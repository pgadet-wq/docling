"""
Mistral AI client with API key management and error handling.
"""

import os
import time
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class MistralClient:
    """Client for Mistral AI API with retry logic and error handling."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "mistral-small-latest",
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize Mistral client.

        Args:
            api_key: Mistral API key (defaults to MISTRAL_API_KEY env var)
            model: Model to use (default: mistral-small-latest)
            max_retries: Maximum number of retries on failure
            retry_delay: Initial delay between retries (exponential backoff)
        """
        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Mistral API key not found. Set MISTRAL_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.model = model
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._client = None

    @property
    def client(self):
        """Lazy initialization of Mistral client."""
        if self._client is None:
            from mistralai import Mistral
            self._client = Mistral(api_key=self.api_key)
        return self._client

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Send a chat request to Mistral.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response
            system_prompt: Optional system prompt to prepend

        Returns:
            The assistant's response text

        Raises:
            Exception: If all retries fail
        """
        # Prepend system prompt if provided
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.complete(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check for rate limit
                if "rate" in error_str or "429" in error_str:
                    wait_time = self.retry_delay * (2 ** attempt)
                    print(f"Rate limited. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue

                # Check for timeout
                if "timeout" in error_str or "timed out" in error_str:
                    wait_time = self.retry_delay * (2 ** attempt)
                    print(f"Timeout. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue

                # For other errors, retry with backoff
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    print(f"Error: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue

                raise

        raise Exception(f"All {self.max_retries} retries failed. Last error: {last_error}")

    def simple_query(self, question: str, system_prompt: Optional[str] = None) -> str:
        """
        Simple single-turn query.

        Args:
            question: The user's question
            system_prompt: Optional system prompt

        Returns:
            The assistant's response
        """
        messages = [{"role": "user", "content": question}]
        return self.chat(messages, system_prompt=system_prompt)
