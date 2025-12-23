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
    ], string='Provider', required=True, default='gemini')

    # Computed field for dynamic help/instructions
    provider_instructions = fields.Html(
        string='Setup Instructions',
        compute='_compute_provider_instructions'
    )

    # ========================================
    # API Keys - Provider Specific
    # ========================================

    # Google Gemini
    gemini_api_key = fields.Char(
        string='API Key',
        groups='ai_agent_core.group_ai_admin',
        help='Get your free API key from: https://aistudio.google.com/apikey (starts with AIza...)'
    )
    gemini_project_id = fields.Char(
        string='Project ID (Vertex AI)',
        help='Only for Vertex AI users. Leave empty if using Google AI Studio API Key.'
    )

    # OpenAI
    openai_api_key = fields.Char(
        string='OpenAI API Key',
        groups='ai_agent_core.group_ai_admin',
        help='Get your API key from: https://platform.openai.com/api-keys'
    )
    openai_org_id = fields.Char(
        string='Organization ID',
        help='Optional: OpenAI Organization ID'
    )

    # Anthropic
    anthropic_api_key = fields.Char(
        string='Anthropic API Key',
        groups='ai_agent_core.group_ai_admin',
        help='Get your API key from: https://console.anthropic.com/settings/keys'
    )

    # Azure OpenAI
    azure_api_key = fields.Char(
        string='Azure API Key',
        groups='ai_agent_core.group_ai_admin',
        help='Azure OpenAI resource key'
    )
    azure_endpoint = fields.Char(
        string='Azure Endpoint',
        help='e.g., https://your-resource.openai.azure.com/'
    )
    azure_deployment = fields.Char(
        string='Deployment Name',
        help='Your Azure deployment name'
    )
    azure_api_version = fields.Char(
        string='API Version',
        default='2024-02-15-preview'
    )

    # Groq
    groq_api_key = fields.Char(
        string='Groq API Key',
        groups='ai_agent_core.group_ai_admin',
        help='Get your API key from: https://console.groq.com/keys'
    )

    # Mistral
    mistral_api_key = fields.Char(
        string='Mistral API Key',
        groups='ai_agent_core.group_ai_admin',
        help='Get your API key from: https://console.mistral.ai/api-keys'
    )

    # Ollama (Local)
    ollama_host = fields.Char(
        string='Ollama Host',
        default='http://localhost:11434',
        help='Ollama server URL (default: http://localhost:11434)'
    )

    # Legacy field for backwards compatibility
    api_key = fields.Char(
        string='API Key (Legacy)',
        groups='ai_agent_core.group_ai_admin',
        help='Deprecated: Use provider-specific API key fields'
    )
    api_base_url = fields.Char(
        string='Custom API URL',
        help='Override the default API endpoint (for proxies)'
    )

    # ========================================
    # Model Configuration
    # ========================================

    default_model = fields.Char(string='Default Model')
    available_models = fields.Text(
        string='Available Models',
        help='Comma-separated list of models'
    )

    # ========================================
    # Connection Status
    # ========================================

    last_test_date = fields.Datetime(string='Last Test', readonly=True)
    last_test_status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
    ], string='Test Status', readonly=True)
    last_test_message = fields.Text(string='Test Message', readonly=True)

    # ========================================
    # Usage Statistics
    # ========================================

    total_tokens_used = fields.Integer(string='Total Tokens', readonly=True, default=0)
    total_requests = fields.Integer(string='Total Requests', readonly=True, default=0)

    @api.depends('provider_type')
    def _compute_provider_instructions(self):
        """Generate setup instructions based on provider type"""
        instructions = {
            'gemini': '''
                <div class="alert alert-info">
                    <h5><i class="fa fa-google"></i> Google Gemini Setup</h5>
                    <ol>
                        <li>Go to <a href="https://aistudio.google.com/apikey" target="_blank">Google AI Studio</a></li>
                        <li>Click "Create API Key" (it's FREE!)</li>
                        <li>Copy the key (starts with <code>AIza...</code>)</li>
                        <li>Paste it in the "API Key" field above</li>
                    </ol>
                    <p><strong>Note:</strong> You only need the API Key. Leave "Project ID" empty unless you're using Vertex AI.</p>
                    <p><strong>Recommended models:</strong> gemini-1.5-flash (fast), gemini-1.5-pro (powerful), gemini-2.0-flash-exp (newest)</p>
                </div>
            ''',
            'openai': '''
                <div class="alert alert-success">
                    <h5><i class="fa fa-bolt"></i> OpenAI Setup</h5>
                    <ol>
                        <li>Go to <a href="https://platform.openai.com/api-keys" target="_blank">OpenAI API Keys</a></li>
                        <li>Click "Create new secret key"</li>
                        <li>Copy and paste the key above</li>
                    </ol>
                    <p><strong>Recommended models:</strong> gpt-4o-mini (cheap), gpt-4o (powerful)</p>
                </div>
            ''',
            'anthropic': '''
                <div class="alert alert-warning">
                    <h5><i class="fa fa-comments"></i> Anthropic Claude Setup</h5>
                    <ol>
                        <li>Go to <a href="https://console.anthropic.com/settings/keys" target="_blank">Anthropic Console</a></li>
                        <li>Create a new API key</li>
                        <li>Copy and paste the key above</li>
                    </ol>
                    <p><strong>Recommended models:</strong> claude-3-5-haiku-latest (fast), claude-3-5-sonnet-latest (balanced)</p>
                </div>
            ''',
            'ollama': '''
                <div class="alert alert-secondary">
                    <h5><i class="fa fa-server"></i> Ollama Local Setup</h5>
                    <ol>
                        <li>Install Ollama: <code>curl -fsSL https://ollama.ai/install.sh | sh</code></li>
                        <li>Pull a model: <code>ollama pull llama3.2</code></li>
                        <li>Ollama should be running at localhost:11434</li>
                    </ol>
                    <p><strong>Popular models:</strong> llama3.2, mistral, codellama, phi3</p>
                    <p><em>No API key required - runs locally on your server!</em></p>
                </div>
            ''',
            'azure_openai': '''
                <div class="alert alert-primary">
                    <h5><i class="fa fa-cloud"></i> Azure OpenAI Setup</h5>
                    <ol>
                        <li>Create an Azure OpenAI resource in Azure Portal</li>
                        <li>Deploy a model (e.g., gpt-4o)</li>
                        <li>Copy the endpoint, key, and deployment name</li>
                    </ol>
                    <p><strong>Required fields:</strong> Endpoint, API Key, Deployment Name</p>
                </div>
            ''',
            'groq': '''
                <div class="alert alert-danger">
                    <h5><i class="fa fa-rocket"></i> Groq Setup (Ultra Fast)</h5>
                    <ol>
                        <li>Go to <a href="https://console.groq.com/keys" target="_blank">Groq Console</a></li>
                        <li>Create an API key</li>
                        <li>Copy and paste the key above</li>
                    </ol>
                    <p><strong>Recommended models:</strong> llama-3.3-70b-versatile, mixtral-8x7b-32768</p>
                    <p><em>Groq offers extremely fast inference!</em></p>
                </div>
            ''',
            'mistral': '''
                <div class="alert alert-info">
                    <h5><i class="fa fa-wind"></i> Mistral AI Setup</h5>
                    <ol>
                        <li>Go to <a href="https://console.mistral.ai/api-keys" target="_blank">Mistral Console</a></li>
                        <li>Create a new API key</li>
                        <li>Copy and paste the key above</li>
                    </ol>
                    <p><strong>Recommended models:</strong> mistral-small-latest (efficient), mistral-large-latest (powerful)</p>
                </div>
            ''',
        }
        for record in self:
            record.provider_instructions = instructions.get(record.provider_type, '')

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

            # Set default host for Ollama
            if self.provider_type == 'ollama' and not self.ollama_host:
                self.ollama_host = 'http://localhost:11434'

    def _get_api_key(self):
        """Get the appropriate API key based on provider type"""
        self.ensure_one()
        key_map = {
            'gemini': self.gemini_api_key,
            'openai': self.openai_api_key,
            'anthropic': self.anthropic_api_key,
            'azure_openai': self.azure_api_key,
            'groq': self.groq_api_key,
            'mistral': self.mistral_api_key,
        }
        # Try provider-specific key first, fall back to legacy api_key
        return key_map.get(self.provider_type) or self.api_key

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

        api_key = self._get_api_key()

        if self.provider_type == 'gemini':
            if not api_key:
                raise ValidationError("Gemini API Key is required")
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=model,
                google_api_key=api_key,
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

        elif self.provider_type == 'openai':
            if not api_key:
                raise ValidationError("OpenAI API Key is required")
            from langchain_openai import ChatOpenAI
            kwargs = {
                'model': model,
                'api_key': api_key,
                'temperature': temperature,
                'max_tokens': max_tokens,
            }
            if self.openai_org_id:
                kwargs['organization'] = self.openai_org_id
            if self.api_base_url:
                kwargs['base_url'] = self.api_base_url
            return ChatOpenAI(**kwargs)

        elif self.provider_type == 'anthropic':
            if not api_key:
                raise ValidationError("Anthropic API Key is required")
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=model,
                api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        elif self.provider_type == 'ollama':
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=model,
                base_url=self.ollama_host or 'http://localhost:11434',
                temperature=temperature,
                num_predict=max_tokens,
            )

        elif self.provider_type == 'azure_openai':
            if not api_key:
                raise ValidationError("Azure API Key is required")
            if not self.azure_endpoint:
                raise ValidationError("Azure Endpoint is required")
            if not self.azure_deployment:
                raise ValidationError("Azure Deployment Name is required")
            from langchain_openai import AzureChatOpenAI
            return AzureChatOpenAI(
                deployment_name=self.azure_deployment,
                api_key=api_key,
                azure_endpoint=self.azure_endpoint,
                api_version=self.azure_api_version or "2024-02-15-preview",
                temperature=temperature,
                max_tokens=max_tokens,
            )

        elif self.provider_type == 'groq':
            if not api_key:
                raise ValidationError("Groq API Key is required")
            from langchain_groq import ChatGroq
            return ChatGroq(
                model=model,
                api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        elif self.provider_type == 'mistral':
            if not api_key:
                raise ValidationError("Mistral API Key is required")
            from langchain_mistralai import ChatMistralAI
            return ChatMistralAI(
                model=model,
                api_key=api_key,
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
