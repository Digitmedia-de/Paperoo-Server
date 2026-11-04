import logging
from typing import Optional
import requests

logger = logging.getLogger(__name__)

class MotivationGenerator:
    """Generate motivational quotes using a configurable LLM provider"""

    PROVIDERS = {'openai', 'anthropic', 'openrouter', 'local'}
    DEFAULTS = {
        'openai': {
            'base_url': 'https://api.openai.com/v1/chat/completions',
            'model': 'gpt-4o-mini',
        },
        'anthropic': {
            'base_url': 'https://api.anthropic.com/v1/messages',
            'model': 'claude-3-5-haiku-latest',
        },
        'openrouter': {
            'base_url': 'https://openrouter.ai/api/v1/chat/completions',
            'model': 'openai/gpt-4o-mini',
        },
        'local': {
            'base_url': 'http://localhost:11434/v1/chat/completions',
            'model': 'llama3.2',
        },
    }

    def __init__(self, config: dict, language: str = 'de'):
        self.provider = config.get('MOTIVATION_PROVIDER', 'openai').lower()
        if self.provider not in self.PROVIDERS:
            self.provider = 'openai'
        self.language = language
        prefix = self.provider.upper()
        defaults = self.DEFAULTS[self.provider]
        self.api_key = config.get(f'{prefix}_API_KEY', '')
        self.base_url = config.get(f'{prefix}_BASE_URL', defaults['base_url'])
        self.model = config.get(f'{prefix}_MODEL', defaults['model'])
        if self.provider == 'local':
            self.enabled = bool(self.base_url and self.model)
        else:
            self.enabled = bool(
                self.api_key
                and self.api_key != 'your-openai-api-key-here'
                and self.base_url
                and self.model
            )

    def _default_message(self, language):
        return 'Pack es an!' if language == 'de' else 'Get it done!'

    def _prompt(self, task, priority, language):
        if language == 'de':
            priority_context = {
                1: 'niedrige Priorität',
                2: 'mittlere Priorität',
                3: 'normale Priorität',
                4: 'hohe Priorität',
                5: 'dringend',
            }
            return f"""Erstelle einen kurzen motivierenden Spruch auf Deutsch für jemanden, der diese Aufgabe mit {priority_context.get(priority, 'normaler Priorität')} erledigen muss: "{task}".
Der Spruch sollte ermutigend, positiv und spezifisch für die Aufgabe sein.
Antworte NUR mit dem motivierenden Spruch, nichts anderes. Keine Anführungszeichen.
Der Spruch sollte zwischen 3 und 10 Wörtern lang sein."""
        priority_context = {
            1: 'low priority',
            2: 'medium priority',
            3: 'normal priority',
            4: 'high priority',
            5: 'urgent',
        }
        return f"""Generate a short motivational phrase in English for someone who needs to complete this {priority_context.get(priority, 'normal priority')} task: "{task}".
The phrase should be encouraging, positive and specific to the task.
Reply ONLY with the motivational phrase, nothing else. No quotes.
The phrase should be between 3 and 10 words."""

    def _request(self, prompt):
        if self.provider == 'anthropic':
            headers = {
                'x-api-key': self.api_key,
                'anthropic-version': '2023-06-01',
                'Content-Type': 'application/json',
            }
            data = {
                'model': self.model,
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 30,
                'temperature': 0.7,
            }
        else:
            headers = {'Content-Type': 'application/json'}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            data = {
                'model': self.model,
                'messages': [
                    {'role': 'system', 'content': 'You are a motivational coach that gives very short, encouraging phrases.'},
                    {'role': 'user', 'content': prompt},
                ],
                'max_tokens': 30,
                'temperature': 0.7,
            }
        return requests.post(self.base_url, headers=headers, json=data, timeout=5)

    def get_motivation(self, task: str, priority: int, language: Optional[str] = None) -> str:
        """Generate a motivational phrase, falling back to the default on failure"""
        lang = language or self.language
        if not self.enabled:
            return self._default_message(lang)

        try:
            response = self._request(self._prompt(task, priority, lang))
            if response.status_code != 200:
                logger.error("Motivation provider %s returned status %s", self.provider, response.status_code)
                return self._default_message(lang)

            result = response.json()
            if self.provider == 'anthropic':
                motivation = result['content'][0]['text'].strip()
            else:
                motivation = result['choices'][0]['message']['content'].strip()
            if not motivation:
                raise ValueError('Empty motivation response')
            return motivation
        except requests.Timeout:
            logger.warning("Motivation provider %s timed out", self.provider)
        except (requests.RequestException, AttributeError, KeyError, IndexError, TypeError, ValueError):
            logger.error("Motivation provider %s returned an unusable response", self.provider)
        return self._default_message(lang)

    def is_enabled(self) -> bool:
        """Check if motivation generation is enabled"""
        return self.enabled
