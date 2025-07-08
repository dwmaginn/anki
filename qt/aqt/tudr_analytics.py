# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""
Tudr Analytics Module
Handles performance tracking, AI-powered topic classification, and daily reporting.
"""

from __future__ import annotations

import json
import re
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anki.cards import Card
    from aqt import AnkiQt
else:
    # Import at runtime to avoid circular imports
    Card = None
    AnkiQt = None

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class TudrAnalytics:
    """Handles performance analytics and reporting for Tudr."""
    
    def __init__(self, mw):
        self.mw = mw
        self.col = mw.col
        self.review_sessions: List[Dict[str, Any]] = []
        self.last_report_date: Optional[str] = None
        self._load_analytics_data()
    
    def _load_analytics_data(self) -> None:
        """Load analytics data from collection config."""
        config = self.col.conf.get("tudrAnalytics", {})
        self.review_sessions = config.get("reviewSessions", [])
        self.last_report_date = config.get("lastReportDate", None)
    
    def _save_analytics_data(self) -> None:
        """Save analytics data to collection config."""
        config = {
            "reviewSessions": self.review_sessions,
            "lastReportDate": self.last_report_date
        }
        self.col.conf["tudrAnalytics"] = config
        self.col.save()
    
    def log_card_review(self, card, ease: int, time_taken: int) -> None:
        """Log a card review for analytics."""
        review_data = {
            "cardId": card.id,
            "ease": ease,
            "timeTaken": time_taken,
            "timestamp": datetime.now().isoformat(),
            "deckId": card.current_deck_id(),
            "question": self._strip_html(card.question()),
            "answer": self._strip_html(card.answer()),
            "noteType": card.note_type()["name"],
            "isCorrect": ease > 1  # Ease 1 is "Again" (incorrect)
        }
        
        self.review_sessions.append(review_data)
        self._save_analytics_data()
    
    def _strip_html(self, text: str) -> str:
        """Strip HTML tags from text."""
        return re.sub('<.*?>', '', text).strip()
    
    def classify_card_topic(self, card_text: str, api_key: str) -> str:
        """Use AI to classify the topic of a card."""
        if not OPENAI_AVAILABLE or not api_key:
            return "Unknown"
        
        prompt = f"""Classify the main topic/subject of this flashcard in 2-3 words.
        
Card content: {card_text[:200]}...

Respond with just the topic name (e.g., "Math - Algebra", "Biology - Cells", "History - World War", "Language - Spanish Vocab", etc.)"""

        try:
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a topic classifier. Respond with just the topic name."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=20,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error classifying topic: {e}")
            return "Unknown"
    
    def get_yesterday_performance(self) -> Dict[str, Any]:
        """Get performance data for yesterday."""
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        total_cards = 0
        correct_cards = 0
        failed_cards = []
        total_time = 0
        
        for session in self.review_sessions:
            session_date = session["timestamp"][:10]  # Get YYYY-MM-DD part
            if session_date == yesterday:
                total_cards += 1
                total_time += session.get("timeTaken", 0)
                
                if session["isCorrect"]:
                    correct_cards += 1
                else:
                    failed_cards.append(session)
        
        accuracy = (correct_cards / total_cards * 100) if total_cards > 0 else 0
        avg_time = (total_time / total_cards) if total_cards > 0 else 0
        
        return {
            "totalCards": total_cards,
            "correctCards": correct_cards,
            "failedCards": len(failed_cards),
            "accuracy": accuracy,
            "avgTime": avg_time,
            "failedCardData": failed_cards
        }
    
    def get_weak_topics(self, failed_cards: List[Dict[str, Any]], api_key: str) -> Dict[str, int]:
        """Analyze failed cards and group by topic."""
        if not failed_cards:
            return {}
        
        topic_counts = defaultdict(int)
        
        for card_data in failed_cards:
            # Try to get topic from note type or deck name first
            note_type = card_data.get("noteType", "")
            deck_name = self._get_deck_name(card_data.get("deckId", 0))
            
            # Use deck name or note type as topic if it's descriptive
            if any(keyword in deck_name.lower() for keyword in ["math", "science", "history", "language", "biology", "chemistry", "physics"]):
                topic = deck_name
            elif any(keyword in note_type.lower() for keyword in ["vocab", "grammar", "formula", "concept"]):
                topic = note_type
            else:
                # Use AI to classify topic
                card_text = f"{card_data['question']} {card_data['answer']}"
                topic = self.classify_card_topic(card_text, api_key)
            
            topic_counts[topic] += 1
        
        # Sort by count, descending
        return dict(sorted(topic_counts.items(), key=lambda x: x[1], reverse=True))
    
    def _get_deck_name(self, deck_id: int) -> str:
        """Get deck name from ID."""
        try:
            deck = self.col.decks.get(deck_id)
            return deck["name"] if deck else "Unknown Deck"
        except:
            return "Unknown Deck"
    
    def generate_daily_report(self) -> str:
        """Generate a daily performance report."""
        today = datetime.now().strftime("%Y-%m-%d")
        
        if self.last_report_date == today:
            return "Daily report already generated for today."
        
        performance = self.get_yesterday_performance()
        
        if performance["totalCards"] == 0:
            return "No cards studied yesterday. Keep up your study routine!"
        
        # Get API key for topic analysis
        api_key = self.col.conf.get("tudrOpenAIKey", "")
        weak_topics = self.get_weak_topics(performance["failedCardData"], api_key)
        
        # Generate report
        report = self._format_daily_report(performance, weak_topics)
        
        # Update last report date
        self.last_report_date = today
        self._save_analytics_data()
        
        return report
    
    def _format_daily_report(self, performance: Dict[str, Any], weak_topics: Dict[str, int]) -> str:
        """Format the daily report text."""
        total = performance["totalCards"]
        correct = performance["correctCards"]
        failed = performance["failedCards"]
        accuracy = performance["accuracy"]
        
        report = f"""🌟 **Tudr Daily Report** - {datetime.now().strftime("%B %d, %Y")}
        
📊 **Yesterday's Performance:**
• Total cards reviewed: {total}
• Correct answers: {correct} ({accuracy:.1f}%)
• Cards to review: {failed}

"""
        
        if weak_topics:
            report += "🎯 **Areas needing attention:**\n"
            for topic, count in list(weak_topics.items())[:3]:  # Top 3 weak topics
                report += f"• {topic}: {count} mistake{'s' if count > 1 else ''}\n"
            report += "\n"
        
        if accuracy >= 90:
            report += "🎉 **Excellent work!** You're mastering your material.\n"
        elif accuracy >= 75:
            report += "👍 **Good progress!** Keep up the consistent effort.\n"
        else:
            report += "💪 **Keep going!** Focus on your weak areas for improvement.\n"
        
        if failed > 0:
            report += f"\n🔄 **Tudr Practice Deck:** {failed} cards have been added to your daily practice deck."
        
        return report
    
    def should_show_daily_report(self) -> bool:
        """Check if daily report should be shown."""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.last_report_date != today and self.get_yesterday_performance()["totalCards"] > 0
    
    def show_daily_report_dialog(self) -> None:
        """Show the daily report in a dialog."""
        from aqt.qt import QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout
        
        report_text = self.generate_daily_report()
        
        dialog = QDialog(self.mw)
        dialog.setWindowTitle("📊 Tudr Daily Report")
        dialog.setMinimumSize(500, 400)
        dialog.resize(600, 500)
        
        layout = QVBoxLayout()
        
        # Text area for report
        text_edit = QTextEdit()
        text_edit.setPlainText(report_text)
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        button_layout.addWidget(close_button)
        
        practice_button = QPushButton("Create Practice Deck")
        practice_button.clicked.connect(lambda: self._create_practice_deck())
        practice_button.clicked.connect(dialog.accept)
        button_layout.addWidget(practice_button)
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.exec()
    
    def _create_practice_deck(self) -> None:
        """Create the Tudr practice deck with failed cards."""
        performance = self.get_yesterday_performance()
        failed_cards = performance["failedCardData"]
        
        if not failed_cards:
            tooltip("No cards to add to practice deck.")
            return
        
        # Create filtered deck with failed card IDs
        card_ids = [str(card["cardId"]) for card in failed_cards]
        search_query = f"cid:{','.join(card_ids)}"
        
        try:
            # Create/update the Tudr practice deck
            deck_id = self._get_or_create_tudr_deck()
            self.col.sched.rebuild_filtered_deck(deck_id, search_query, 0)
            
            tooltip(f"Added {len(failed_cards)} cards to Tudr Practice Deck!")
        except Exception as e:
            tooltip(f"Error creating practice deck: {str(e)}")
    
    def _get_or_create_tudr_deck(self) -> int:
        """Get or create the Tudr practice deck."""
        deck_name = "Tudr - Daily Practice"
        
        # Check if deck exists
        for deck_id, deck in self.col.decks.decks.items():
            if deck["name"] == deck_name:
                return int(deck_id)
        
        # Create new filtered deck
        deck_id = self.col.decks.new_filtered(deck_name)
        return deck_id


# Global analytics instance
_analytics_instance: Optional[TudrAnalytics] = None

def get_analytics(mw) -> TudrAnalytics:
    """Get or create the global analytics instance."""
    global _analytics_instance
    if _analytics_instance is None:
        _analytics_instance = TudrAnalytics(mw)
    return _analytics_instance

def log_review(mw, card, ease: int, time_taken: int = 0) -> None:
    """Convenience function to log a card review."""
    analytics = get_analytics(mw)
    analytics.log_card_review(card, ease, time_taken)

def check_and_show_daily_report(mw) -> None:
    """Check if daily report should be shown and display it."""
    analytics = get_analytics(mw)
    if analytics.should_show_daily_report():
        analytics.show_daily_report_dialog()