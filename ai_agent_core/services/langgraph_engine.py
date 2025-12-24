# -*- coding: utf-8 -*-
from odoo import models, api
import json
import time
import logging

_logger = logging.getLogger(__name__)

try:
    from langgraph.graph import StateGraph, START, END
    from langgraph.prebuilt import ToolNode, tools_condition
    from langgraph.checkpoint.memory import MemorySaver
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
    from typing import Annotated, TypedDict
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    _logger.warning("LangGraph not installed. AI features will be limited.")


class LangGraphEngine(models.AbstractModel):
    _name = 'ai.langgraph.engine'
    _description = 'LangGraph Processing Engine'

    def _check_dependencies(self):
        """Check if required dependencies are available"""
        if not LANGGRAPH_AVAILABLE:
            raise ImportError(
                "LangGraph is required but not installed. "
                "Please install with: pip install langgraph langchain-core langchain-google-genai"
            )

    @api.model
    def process_message(self, agent, message, context=None, conversation=None, debug=False):
        """
        Process a message using LangGraph

        Args:
            agent: ai.agent record
            message: User message string
            context: Additional context dictionary
            conversation: ai.conversation record (optional)
            debug: Include debug information in response

        Returns:
            Dictionary with response and metadata
        """
        self._check_dependencies()

        start_time = time.time()
        context = context or {}

        # Get or create conversation
        if not conversation:
            conversation = self._get_or_create_conversation(agent, context)

        # Add user message to conversation
        conversation.add_message('user', message)

        # Check for triggered rules
        triggered_rules = agent.get_triggered_rules(message, context)
        rule_instructions = '\n'.join(
            rule.get_action_prompt() for rule in triggered_rules
            if rule.action_type in ['instruction', 'activity', 'response']
        )

        # Build enhanced context with rules
        enhanced_context = context.copy()
        if rule_instructions:
            enhanced_context['additional_instructions'] = rule_instructions

        try:
            # Get tools
            tools = agent.get_langchain_tools(self.env)

            # Build and execute graph
            result = self._execute_graph(
                agent=agent,
                message=message,
                context=enhanced_context,
                conversation=conversation,
                tools=tools
            )

            # Extract response
            response_text = self._extract_response(result)

            # Save assistant response
            processing_time = time.time() - start_time
            conversation.add_message(
                'assistant',
                response_text,
                metadata={
                    'processing_time': processing_time,
                    'model': agent.model_name or agent.provider_id.default_model,
                    'tools_called': result.get('tools_called', []),
                }
            )

            # Update provider usage stats
            agent.provider_id.increment_usage(requests=1)

            output = {
                'response': response_text,
                'conversation_id': conversation.id,
                'tools_called': result.get('tools_called', []),
                'triggered_rules': triggered_rules.mapped('name'),
                'processing_time': processing_time,
            }

            if debug:
                output['debug'] = {
                    'system_prompt': agent.build_system_prompt(enhanced_context),
                    'tools_available': [t.name for t in tools] if tools else [],
                    'raw_result': str(result),
                }

            return output

        except Exception as e:
            _logger.exception(f"Error processing message with agent {agent.name}")

            # Save error as system message
            conversation.add_message(
                'system',
                f"Error: {str(e)}",
                metadata={'error': True}
            )

            return {
                'response': agent.fallback_response or "Lo siento, ocurrió un error al procesar tu mensaje.",
                'conversation_id': conversation.id,
                'error': str(e),
                'processing_time': time.time() - start_time,
            }

    def _get_or_create_conversation(self, agent, context):
        """Get existing conversation or create new one"""
        channel_ref = context.get('channel_reference')
        channel_type = context.get('channel', 'web')

        if channel_ref:
            conversation = self.env['ai.conversation'].search([
                ('channel_reference', '=', channel_ref),
                ('agent_id', '=', agent.id),
                ('state', 'in', ['active', 'waiting'])
            ], limit=1)

            if conversation:
                return conversation

        # Create new conversation
        return self.env['ai.conversation'].create({
            'agent_id': agent.id,
            'channel_type': channel_type,
            'channel_reference': channel_ref,
            'partner_id': context.get('partner_id'),
            'external_user_id': context.get('external_user_id'),
            'external_user_name': context.get('external_user_name'),
            'context_data': json.dumps(context),
        })

    def _execute_graph(self, agent, message, context, conversation, tools):
        """
        Build and execute the LangGraph

        Args:
            agent: ai.agent record
            message: User message
            context: Context dictionary
            conversation: ai.conversation record
            tools: List of LangChain tools

        Returns:
            Execution result
        """
        # Define state type
        class AgentState(TypedDict):
            messages: list
            context: dict
            tools_called: list

        # Get LLM from provider
        llm = agent.provider_id._get_llm_client(
            model=agent.model_name,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens
        )

        # Bind tools if available
        if tools:
            llm_with_tools = llm.bind_tools(tools)
        else:
            llm_with_tools = llm

        # Build system prompt
        system_prompt = agent.build_system_prompt(context)

        # Define agent node
        def agent_node(state: AgentState):
            messages = [SystemMessage(content=system_prompt)]

            # Add conversation history if memory enabled
            if agent.enable_memory and conversation:
                history = conversation.get_message_history(limit=agent.memory_window)
                for msg in history[:-1]:  # Exclude current message
                    if msg['role'] == 'user':
                        messages.append(HumanMessage(content=msg['content']))
                    elif msg['role'] == 'assistant':
                        messages.append(AIMessage(content=msg['content']))

            # Add current message
            messages.append(HumanMessage(content=state['messages'][-1]['content']))

            # Invoke LLM
            response = llm_with_tools.invoke(messages)

            return {
                'messages': state['messages'] + [{'role': 'assistant', 'content': response}],
                'tools_called': state.get('tools_called', [])
            }

        # Define tool node wrapper
        def tool_node_wrapper(state: AgentState):
            last_message = state['messages'][-1]
            if isinstance(last_message, dict):
                last_message = last_message.get('content')

            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                tool_node = ToolNode(tools=tools)
                tool_results = []

                for tool_call in last_message.tool_calls:
                    tool_name = tool_call.get('name')
                    tool_args = tool_call.get('args', {})

                    # Find and execute tool
                    for tool in tools:
                        if tool.name == tool_name:
                            try:
                                result = tool.invoke(tool_args)
                                tool_results.append({
                                    'tool': tool_name,
                                    'args': tool_args,
                                    'result': result
                                })
                            except Exception as e:
                                tool_results.append({
                                    'tool': tool_name,
                                    'args': tool_args,
                                    'error': str(e)
                                })

                return {
                    'messages': state['messages'],
                    'tools_called': state.get('tools_called', []) + tool_results
                }

            return state

        # Define should_continue function
        def should_continue(state: AgentState):
            last_message = state['messages'][-1]
            if isinstance(last_message, dict):
                content = last_message.get('content')
            else:
                content = last_message

            if hasattr(content, 'tool_calls') and content.tool_calls:
                return "tools"
            return END

        # Build graph
        builder = StateGraph(AgentState)

        builder.add_node("agent", agent_node)
        if tools:
            builder.add_node("tools", tool_node_wrapper)
            builder.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
            builder.add_edge("tools", "agent")
        else:
            builder.add_edge("agent", END)

        builder.add_edge(START, "agent")

        # Compile with memory checkpointer
        memory = MemorySaver()
        graph = builder.compile(checkpointer=memory)

        # Execute
        thread_id = str(conversation.id) if conversation else "default"
        config = {"configurable": {"thread_id": thread_id}}

        initial_state = {
            "messages": [{"role": "user", "content": message}],
            "context": context,
            "tools_called": []
        }

        result = graph.invoke(initial_state, config=config)

        return result

    def _extract_response(self, result):
        """Extract the final response text from graph result"""
        messages = result.get('messages', [])

        if not messages:
            return "No response generated"

        last_message = messages[-1]

        # Handle different message formats
        if isinstance(last_message, dict):
            content = last_message.get('content')
            if hasattr(content, 'content'):
                return content.content
            return str(content)
        elif hasattr(last_message, 'content'):
            if hasattr(last_message.content, 'content'):
                return last_message.content.content
            return last_message.content
        else:
            return str(last_message)

    @api.model
    def test_connection(self, provider_id):
        """Test LLM connection"""
        self._check_dependencies()

        provider = self.env['ai.agent.provider'].browse(provider_id)
        if not provider.exists():
            return {'success': False, 'error': 'Provider not found'}

        try:
            llm = provider._get_llm_client()
            response = llm.invoke("Say 'Hello' in one word")
            return {
                'success': True,
                'response': response.content if hasattr(response, 'content') else str(response)
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
