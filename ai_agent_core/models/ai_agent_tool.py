# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


class AIAgentTool(models.Model):
    _name = 'ai.agent.tool'
    _description = 'AI Agent Tool'
    _order = 'sequence, name'

    name = fields.Char(string='Tool Name', required=True)
    technical_name = fields.Char(
        string='Technical Name',
        required=True,
        help='Internal name used in code (e.g., search_products)'
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    description = fields.Text(
        string='Description',
        required=True,
        help='Description shown to the AI model explaining what this tool does'
    )

    # Tool type
    tool_type = fields.Selection([
        ('builtin', 'Built-in Odoo Tool'),
        ('python', 'Custom Python Code'),
        ('http_api', 'HTTP API Call'),
        ('mcp_server', 'MCP Server'),
    ], string='Tool Type', default='builtin', required=True)

    # Category for organization
    category = fields.Selection([
        ('sales', 'Sales'),
        ('crm', 'CRM'),
        ('inventory', 'Inventory'),
        ('accounting', 'Accounting'),
        ('contacts', 'Contacts'),
        ('products', 'Products'),
        ('general', 'General'),
        ('custom', 'Custom'),
    ], string='Category', default='general')

    # For builtin tools - which Odoo model/method to call
    odoo_model = fields.Char(string='Odoo Model')
    odoo_method = fields.Char(string='Method Name')

    # For custom Python code
    python_code = fields.Text(
        string='Python Code',
        help='Custom Python code to execute. Use `env` for Odoo environment, `params` for input parameters.'
    )

    # For HTTP API
    api_endpoint = fields.Char(string='API Endpoint')
    api_method = fields.Selection([
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('DELETE', 'DELETE'),
    ], string='HTTP Method', default='POST')
    api_headers = fields.Text(
        string='API Headers',
        help='JSON format headers'
    )
    api_body_template = fields.Text(
        string='Body Template',
        help='JSON template with {{param}} placeholders'
    )

    # For MCP Server
    mcp_server_url = fields.Char(string='MCP Server URL')
    mcp_tool_name = fields.Char(string='MCP Tool Name')
    mcp_auth_token = fields.Char(string='MCP Auth Token', groups='ai_agent_core.group_ai_admin')

    # Parameters definition (JSON schema)
    parameters_schema = fields.Text(
        string='Parameters Schema',
        help='JSON Schema defining the tool parameters',
        default='{"type": "object", "properties": {}, "required": []}'
    )

    # Return value handling
    return_format = fields.Selection([
        ('text', 'Plain Text'),
        ('json', 'JSON'),
        ('markdown', 'Markdown'),
    ], string='Return Format', default='text')

    # Security
    requires_confirmation = fields.Boolean(
        string='Requires Confirmation',
        default=False,
        help='If checked, tool execution will require human approval'
    )
    allowed_group_ids = fields.Many2many(
        'res.groups',
        string='Allowed Groups',
        help='Groups that can use this tool. Empty means all.'
    )

    _sql_constraints = [
        ('technical_name_unique', 'UNIQUE(technical_name)', 'Technical name must be unique!')
    ]

    @api.model
    def create(self, vals):
        if 'technical_name' in vals:
            vals['technical_name'] = vals['technical_name'].lower().replace(' ', '_')
        return super().create(vals)

    def write(self, vals):
        if 'technical_name' in vals:
            vals['technical_name'] = vals['technical_name'].lower().replace(' ', '_')
        return super().write(vals)

    def get_langchain_tool(self, env):
        """
        Returns a LangChain tool definition for this tool

        Args:
            env: Odoo environment

        Returns:
            LangChain tool function
        """
        self.ensure_one()

        from langchain_core.tools import tool

        tool_record = self
        params_schema = json.loads(self.parameters_schema or '{}')

        # Create dynamic tool function
        def tool_executor(**kwargs):
            return tool_record._execute(env, kwargs)

        # Set function metadata
        tool_executor.__name__ = self.technical_name
        tool_executor.__doc__ = self.description

        # Wrap with LangChain tool decorator
        return tool(tool_executor)

    def _execute(self, env, params):
        """
        Execute the tool with given parameters

        Args:
            env: Odoo environment
            params: Dictionary of parameters

        Returns:
            Tool execution result as string
        """
        self.ensure_one()

        try:
            if self.tool_type == 'builtin':
                return self._execute_builtin(env, params)
            elif self.tool_type == 'python':
                return self._execute_python(env, params)
            elif self.tool_type == 'http_api':
                return self._execute_http(params)
            elif self.tool_type == 'mcp_server':
                return self._execute_mcp(params)
            else:
                return f"Unknown tool type: {self.tool_type}"

        except Exception as e:
            _logger.exception(f"Error executing tool {self.technical_name}")
            return f"Error executing tool: {str(e)}"

    def _execute_builtin(self, env, params):
        """Execute built-in Odoo tool"""
        if not self.odoo_model or not self.odoo_method:
            return "Tool not properly configured: missing model or method"

        model = env.get(self.odoo_model)
        if not model:
            return f"Model {self.odoo_model} not found"

        method = getattr(model, self.odoo_method, None)
        if not method:
            return f"Method {self.odoo_method} not found on {self.odoo_model}"

        return method(**params)

    def _execute_python(self, env, params):
        """Execute custom Python code"""
        if not self.python_code:
            return "No Python code defined"

        # Safe execution context
        local_vars = {
            'env': env,
            'params': params,
            'result': None,
            'json': json,
        }

        try:
            exec(self.python_code, {'__builtins__': {}}, local_vars)
            return local_vars.get('result', 'No result returned')
        except Exception as e:
            return f"Python execution error: {str(e)}"

    def _execute_http(self, params):
        """Execute HTTP API call"""
        import requests

        if not self.api_endpoint:
            return "No API endpoint configured"

        headers = json.loads(self.api_headers or '{}')

        # Build body from template
        body = self.api_body_template or '{}'
        for key, value in params.items():
            body = body.replace('{{%s}}' % key, str(value))

        try:
            body_json = json.loads(body)
        except json.JSONDecodeError:
            body_json = {}

        response = requests.request(
            method=self.api_method,
            url=self.api_endpoint,
            headers=headers,
            json=body_json if self.api_method in ['POST', 'PUT'] else None,
            params=body_json if self.api_method == 'GET' else None,
            timeout=30
        )

        if response.ok:
            try:
                return json.dumps(response.json(), indent=2)
            except json.JSONDecodeError:
                return response.text
        else:
            return f"HTTP Error {response.status_code}: {response.text[:500]}"

    def _execute_mcp(self, params):
        """Execute MCP Server tool call"""
        import requests

        if not self.mcp_server_url or not self.mcp_tool_name:
            return "MCP Server not properly configured"

        headers = {'Content-Type': 'application/json'}
        if self.mcp_auth_token:
            headers['Authorization'] = f'Bearer {self.mcp_auth_token}'

        payload = {
            'jsonrpc': '2.0',
            'method': 'tools/call',
            'params': {
                'name': self.mcp_tool_name,
                'arguments': params
            },
            'id': 1
        }

        try:
            response = requests.post(
                self.mcp_server_url,
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.ok:
                result = response.json()
                if 'result' in result:
                    content = result['result'].get('content', [])
                    if content and isinstance(content, list):
                        return content[0].get('text', str(result))
                    return str(result['result'])
                elif 'error' in result:
                    return f"MCP Error: {result['error']}"
            return f"MCP request failed: {response.status_code}"

        except Exception as e:
            return f"MCP execution error: {str(e)}"

    def action_test_tool(self):
        """Test tool with sample parameters"""
        self.ensure_one()

        # Get sample params from schema
        schema = json.loads(self.parameters_schema or '{}')
        sample_params = {}

        for prop_name, prop_def in schema.get('properties', {}).items():
            prop_type = prop_def.get('type', 'string')
            if prop_type == 'string':
                sample_params[prop_name] = prop_def.get('default', 'test')
            elif prop_type == 'integer':
                sample_params[prop_name] = prop_def.get('default', 1)
            elif prop_type == 'number':
                sample_params[prop_name] = prop_def.get('default', 1.0)
            elif prop_type == 'boolean':
                sample_params[prop_name] = prop_def.get('default', True)

        result = self._execute(self.env, sample_params)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': f'Tool Test: {self.name}',
                'message': str(result)[:500],
                'type': 'info',
                'sticky': True,
            }
        }
