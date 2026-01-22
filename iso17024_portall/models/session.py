from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class CertUserSession(models.Model):
    """User Session Tracking for Multi-Device Detection"""
    _name = 'cert.user.session'
    _description = 'User Session Tracking'
    _order = 'login_time desc'

    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade')
    session_token = fields.Char(string='Session Token', required=True, index=True)
    ip_address = fields.Char(string='IP Address')
    user_agent = fields.Text(string='User Agent')
    device_fingerprint = fields.Char(string='Device Fingerprint')
    login_time = fields.Datetime(string='Login Time', default=fields.Datetime.now)
    last_activity = fields.Datetime(string='Last Activity')
    is_active = fields.Boolean(string='Active', default=True, index=True)
    logout_reason = fields.Selection([
        ('manual', 'Manual Logout'),
        ('new_device', 'Login dari device lain'),
        ('expired', 'Session Expired'),
        ('admin', 'Admin Force Logout'),
    ], string='Logout Reason')
    logout_time = fields.Datetime(string='Logout Time')

    def deactivate_session(self, reason='manual'):
        """Deactivate this session"""
        self.write({
            'is_active': False,
            'logout_reason': reason,
            'logout_time': fields.Datetime.now()
        })

    @api.model
    def create_session(self, user_id, session_token, ip_address=None, user_agent=None, device_fingerprint=None):
        """Create new session and deactivate old ones for this user"""
        # Deactivate all existing active sessions for this user
        old_sessions = self.search([
            ('user_id', '=', user_id),
            ('is_active', '=', True)
        ])

        if old_sessions:
            old_sessions.deactivate_session('new_device')
            _logger.info(f"Deactivated {len(old_sessions)} old sessions for user {user_id}")

        # Create new session
        new_session = self.create({
            'user_id': user_id,
            'session_token': session_token,
            'ip_address': ip_address or '',
            'user_agent': user_agent or '',
            'device_fingerprint': device_fingerprint or '',
        })

        _logger.info(f"Created new session for user {user_id}: {session_token[:20]}...")
        return new_session

    @api.model
    def validate_session(self, user_id, session_token, auto_create=True):
        """Check if session is still valid (active)

        Args:
            user_id: User ID to check
            session_token: Current session token
            auto_create: If True, auto-create/fix session automatically
        """
        if not session_token:
            _logger.warning(f"Empty session token for user {user_id}")
            return False

        # Check if this exact session is active
        session = self.search([
            ('user_id', '=', user_id),
            ('session_token', '=', session_token),
            ('is_active', '=', True)
        ], limit=1)

        if session:
            # Update last activity
            session.write({'last_activity': fields.Datetime.now()})
            return True

        # Check if user has any OTHER ACTIVE session (different token = another device)
        other_active_session = self.search([
            ('user_id', '=', user_id),
            ('is_active', '=', True)
        ], limit=1)

        if other_active_session:
            # Check if the other session has recent activity (within last 5 minutes)
            # If not, it's probably a stale session - just replace it
            from datetime import timedelta
            five_minutes_ago = fields.Datetime.now() - timedelta(minutes=5)

            if other_active_session.last_activity and other_active_session.last_activity > five_minutes_ago:
                # Genuinely active on another device
                _logger.warning(f"Multi-device detected for user {user_id}. Other session active at {other_active_session.last_activity}")
                return False
            else:
                # Stale session - deactivate it and create new one
                _logger.info(f"Replacing stale session for user {user_id}")
                other_active_session.deactivate_session('expired')

        # Auto-create new session
        if auto_create:
            _logger.info(f"Creating session for user {user_id}")
            self.create({
                'user_id': user_id,
                'session_token': session_token,
                'ip_address': '',
                'user_agent': 'Auto-created',
                'last_activity': fields.Datetime.now(),
            })
            return True

        return False

    @api.model
    def get_active_session(self, user_id):
        """Get current active session for user"""
        return self.search([
            ('user_id', '=', user_id),
            ('is_active', '=', True)
        ], limit=1)

    def action_force_logout(self):
        """Admin action to force logout a session"""
        self.deactivate_session('admin')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Session Terminated',
                'message': f'Session untuk {self.user_id.name} telah diakhiri.',
                'type': 'success',
            }
        }

    def action_clear_all_user_sessions(self):
        """Admin action to clear ALL sessions for this user"""
        user = self.user_id
        all_sessions = self.search([('user_id', '=', user.id)])
        count = len(all_sessions)
        all_sessions.unlink()  # Delete completely, not just deactivate
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sessions Cleared',
                'message': f'Semua {count} session untuk {user.name} telah dihapus. User perlu login ulang.',
                'type': 'success',
            }
        }
