# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class AIAgentProvider(models.Model):
    _name = 'ai.agent.provider'
    _description = 'AI LLM Provider Configuration'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    provider_type = fields.Selection([
        ('gemini', 'Google Gemini'),
        ('openai', 'OpenAI'),
        ('anthropic', 'Anthropic Claude'),
        ('ollama', 'Ollama (Local)'),
        ('azure_openai', 'Azure OpenAI'),
        ('groq', 'Groq'),
        ('mistral', 'Mistral AI'),
    ], string='Provider Type', required=True, default='gemini')

    # API Configuration
    api_key = fields.Char(string='API Key', groups='ai_agent_core.group_ai_admin')
    api_base_url = fields.Char(string='API Base URL', help='Custom API endpoint (for Ollama, Azure, etc.)')

    # Default model for this provider
    default_model = fields.Char(string='Default Model')

    # Available models (computed or manual)
    available_models = fields.Text(
        string='Available Models',
        help='Comma-separated list of available models for this provider'
    )

    # Connection test
    last_test_date = fields.Datetime(string='Last Test', readonly=True)
    last_test_status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
    ], string='Test Status', readonly=True)
    last_test_message = fields.Text(string='Test Message', readonly=True)

    # Usage tracking
    total_tokens_used = fields.Integer(string='Total Tokens Used', readonly=True, default=0)
    total_requests = fields.Integer(string='Total Requests', readonly=True, default=0)

    @api.model
    def _get_default_models(self, provider_type):
        """Returns default models for each provider"""
        defaults = {
            'gemini': 'gemini-1.5-flash,gemini-1.5-pro,gemini-2.0-flash-exp',
            'openai': 'gpt-4o,gpt-4o-mini,gpt-4-turbo,gpt-3.5-turbo',
            'anthropic': 'claude-3-5-sonnet-latest,claude-3-5-haiku-latest,claude-3-opus-latest',
            'ollama': 'llama3.2,mistral,codellama,phi3',
            'azure_openai': 'gpt-4o,gpt-4-turbo',
            'groq': 'llama-3.3-70b-versatile,mixtral-8x7b-32768',
            'mistral': 'mistral-large-latest,mistral-small-latest',
        }
        return defaults.get(provider_type, '')

    @api.onchange('provider_type')
    def _onchange_provider_type(self):
        """Set default values based on provider type"""
        if self.provider_type:
            self.available_models = self._get_default_models(self.provider_type)

            # Set default model
            models_list = self.available_models.split(',') if self.available_models else []
            self.default_model = models_list[0].strip() if models_list else ''

            # Set default base URL for Ollama
            if self.provider_type == 'ollama' and not self.api_base_url:
                self.api_base_url = 'http://localhost:11434'

    def get_model_list(self):
        """Returns list of available models"""
        self.ensure_one()
        if not self.available_models:
            return []
        return [m.strip() for m in self.available_models.split(',') if m.strip()]

    def action_test_connection(self):
        """Test connection to the LLM provider"""
        self.ensure_one()

        try:
            llm = self._get_llm_client(model=self.default_model)

            # Simple test message
            response = llm.invoke("Say 'Connection successful' in exactly those words.")

            self.write({
                'last_test_date': fields.Datetime.now(),
                'last_test_status': 'success',
                'last_test_message': f"Connected successfully. Response: {str(response.content)[:200]}"
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Test',
                    'message': 'Connection successful!',
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            self.write({
                'last_test_date': fields.Datetime.now(),
                'last_test_status': 'failed',
                'last_test_message': str(e)
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Test Failed',
                    'message': str(e)[:200],
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def _get_llm_client(self, model=None, temperature=0.7, max_tokens=2000):
        """
        Returns configured LLM client for this provider

        Args:
            model: Model name to use (defaults to provider's default_model)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response

        Returns:
            LangChain chat model instance
        """
        self.ensure_one()

        model = model or self.default_model
        if not model:
            raise ValidationError(f"No model specified for provider {self.name}")

        if self.provider_type == 'gemini':
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=model,
                google_api_key=self.api_key,
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

        elif self.provider_type == 'openai':
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model,
                api_key=self.api_key,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        elif self.provider_type == 'anthropic':
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=model,
                api_key=self.api_key,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        elif self.provider_type == 'ollama':
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=model,
                base_url=self.api_base_url or 'http://localhost:11434',
                temperature=temperature,
                num_predict=max_tokens,
            )

        elif self.provider_type == 'azure_openai':
            from langchain_openai import AzureChatOpenAI
            return AzureChatOpenAI(
                deployment_name=model,
                api_key=self.api_key,
                azure_endpoint=self.api_base_url,
                api_version="2024-02-15-preview",
                temperature=temperature,
                max_tokens=max_tokens,
            )

        elif self.provider_type == 'groq':
            from langchain_groq import ChatGroq
            return ChatGroq(
                model=model,
                api_key=self.api_key,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        elif self.provider_type == 'mistral':
            from langchain_mistralai import ChatMistralAI
            return ChatMistralAI(
                model=model,
                api_key=self.api_key,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        else:
            raise ValidationError(f"Unsupported provider type: {self.provider_type}")

    def increment_usage(self, tokens=0, requests=1):
        """Increment usage counters"""
        self.ensure_one()
        self.sudo().write({
            'total_tokens_used': self.total_tokens_used + tokens,
            'total_requests': self.total_requests + requests,
        })
