import os
import logging
import json
from typing import Optional
import requests

logger = logging.getLogger(__name__)

class MotivationGenerator:
    """Generate motivational quotes using OpenAI API"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", language: str = "de"):
        self.api_key = api_key
        self.model = model
        self.language = language
        self.enabled = bool(api_key and api_key != "your-openai-api-key-here")
        
    def get_motivation(self, task: str, priority: int, language: Optional[str] = None) -> str:
        """Generate a motivational quote based on the task with optional language override"""
        if not self.enabled:
            lang = language if language else self.language
            if lang == 'de':
                return "Pack es an!"
            return "Get it done!"
        
        try:
            # Use override language if provided, otherwise use instance language
            lang = language if language else self.language
            
            # Create priority context based on language
            if lang == 'de':
                priority_context = {
                    1: "niedrige Priorität",
                    2: "mittlere Priorität", 
                    3: "normale Priorität",
                    4: "hohe Priorität",
                    5: "dringend"
                }
                prompt = f"""Erstelle einen kurzen motivierenden Spruch auf Deutsch für jemanden, der diese Aufgabe mit {priority_context.get(priority, 'normaler Priorität')} erledigen muss: "{task}". 
                Der Spruch sollte ermutigend, positiv und spezifisch für die Aufgabe sein. 
                Antworte NUR mit dem motivierenden Spruch, nichts anderes. Keine Anführungszeichen.
                Der Spruch sollte zwischen 3 und 10 Wörtern lang sein.
                Beispiele: "Du schaffst das heute noch!", "Ran an die Arbeit, Champion!", "Erfolg wartet auf dich!", "Zeit zu glänzen!"."""
            else:
                priority_context = {
                    1: "low priority",
                    2: "medium priority", 
                    3: "normal priority",
                    4: "high priority",
                    5: "urgent"
                }
                prompt = f"""Generate a short motivational phrase in English for someone who needs to complete this {priority_context.get(priority, 'normal priority')} task: "{task}". 
                The phrase should be encouraging, positive and specific to the task. 
                Reply ONLY with the motivational phrase, nothing else. No quotes.
                The phrase should be between 3 and 10 words.
                Examples: "You've got this today!", "Make it happen, champion!", "Success awaits you!", "Time to shine!"."""
            
            # Make API request
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a motivational coach that gives very short, encouraging phrases."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 30,
                "temperature": 0.7
            }
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=5  # 5 second timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                motivation = result['choices'][0]['message']['content'].strip()
                # Don't limit the length - show full motivation as OpenAI returns it
                logger.info(f"Generated motivation: {motivation}")
                return motivation
            else:
                logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
                if lang == 'de':
                    return "Pack es an!"
                return "Get it done!"
                
        except requests.Timeout:
            logger.warning("OpenAI API timeout - using default message")
            if lang == 'de':
                return "Pack es an!"
            return "Get it done!"
        except Exception as e:
            logger.error(f"Error generating motivation: {str(e)}")
            if lang == 'de':
                return "Pack es an!"
            return "Get it done!"
    
    def is_enabled(self) -> bool:
        """Check if motivation generation is enabled"""
        return self.enabled