import subprocess
import logging
import shlex

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PipCommands(models.TransientModel):
    _name = 'pip.command'
    _description = 'Install Python Library'

    library_name = fields.Char(string='Library Name', required=True)
    pip_versions = fields.Selection(
        selection=[
            ('pip', 'pip'),
            ('pip3', 'pip3'),
        ],
        string='Pip Version',
        default='pip3',
        required=True,
    )

    @api.constrains('library_name')
    def _check_library_name(self):
        for record in self:
            if record.library_name:
                # Validate library name to prevent command injection
                invalid_chars = [';', '&', '|', '`', '$', '(', ')', '{', '}', '<', '>', '\n', '\r']
                for char in invalid_chars:
                    if char in record.library_name:
                        raise UserError(_('Invalid character in library name: %s') % char)

    def install_button(self):
        self.ensure_one()
        if not self.library_name:
            raise UserError(_('Please enter a library name'))

        msg = ''
        try:
            # Sanitize library name
            library_name = shlex.quote(self.library_name.strip())
            command = [self.pip_versions, 'install', self.library_name.strip()]

            _logger.info('Installing Python library: %s', self.library_name)

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0:
                output = result.stdout.replace('\n', '<br/>')
                msg = f'<div class="alert alert-success" role="alert">{output}</div>'
                _logger.info('Successfully installed: %s', self.library_name)
            else:
                output = result.stderr.replace('\n', '<br/>')
                msg = f'<div class="alert alert-danger" role="alert">Error: {output}</div>'
                _logger.warning('Failed to install %s: %s', self.library_name, result.stderr)

        except subprocess.TimeoutExpired:
            msg = '<div class="alert alert-warning" role="alert">Installation timed out after 5 minutes</div>'
            _logger.error('Installation timeout for: %s', self.library_name)
        except Exception as e:
            msg = f'<div class="alert alert-danger" role="alert">Error: {str(e)}</div>'
            _logger.exception('Error installing %s', self.library_name)

        if not msg:
            msg = '<div class="alert alert-info" role="alert">Nothing to install</div>'

        message_id = self.env['message.wizard'].create({'message': msg})
        return {
            'name': _('Installation Result'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'message.wizard',
            'res_id': message_id.id,
            'target': 'new',
        }