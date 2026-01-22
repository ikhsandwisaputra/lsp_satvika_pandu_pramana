from odoo import http, _, fields
from odoo.http import request
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
import base64

class IsoPortalController(AuthSignupHome):

    # ---------------------------------------------------------
    # HELPER: Smart redirect untuk user yang sudah login
    # ---------------------------------------------------------
    def _get_smart_redirect_url(self, partner):
        """Determine the correct URL for a logged-in user based on their application state"""
        # Cek status registrasi
        if partner.registration_state == 'pending':
            return '/certification/pending'
        
        # Cari application yang ada
        app = request.env['certification.application'].search([
            ('partner_id', '=', partner.id)
        ], limit=1)
        
        if not app:
            # Belum punya application → ke apply (step 1)
            return '/certification/apply'
        
        # Kalau state bukan draft → ke status page
        if app.state not in ['draft']:
            return '/certification/status'
        
        # Kalau draft, cek step
        if app.current_step >= 2:
            return '/certification/apply/step2'
        
        # Default: step 1
        return '/certification/apply'

    # ---------------------------------------------------------
    # ROUTE: Pengajuan Sertifikasi - Smart Redirect
    # ---------------------------------------------------------
    @http.route('/pengajuan-sertifikasi', type='http', auth='public', website=True)
    def pengajuan_sertifikasi(self, **kw):
        """
        Halaman pilih jenis sertifikasi.
        - Internal user (admin): tampilkan halaman (untuk edit snippet)
        - Public user: tampilkan halaman pilih jenis (snippet)
        - Portal user (kandidat): redirect ke apply/step2/status sesuai state
        """
        user = request.env.user
        
        # Internal user (admin) → render halaman untuk edit snippet
        if user.has_group('base.group_user'):
            return request.render('iso17024_portall.pengajuan_sertifikasi_page')
        
        # Portal user (kandidat) → smart redirect
        if not user._is_public():
            partner = user.partner_id
            return request.redirect(self._get_smart_redirect_url(partner))
        
        # Public user → render halaman dengan snippet
        return request.render('iso17024_portall.pengajuan_sertifikasi_page')

    # ---------------------------------------------------------
    # ROUTE: Pilih Level - Smart Redirect  
    # ---------------------------------------------------------
    @http.route('/pilih-level', type='http', auth='public', website=True)
    def pilih_level(self, **kw):
        """
        Halaman pilih level sertifikasi.
        - Internal user (admin): tampilkan halaman (untuk edit snippet)
        - Public user: tampilkan halaman pilih level (snippet)
        - Portal user (kandidat): redirect ke apply/step2/status sesuai state
        """
        user = request.env.user
        
        # Internal user (admin) → render halaman untuk edit snippet
        if user.has_group('base.group_user'):
            return request.render('iso17024_portall.pilih_level_page')
        
        # Portal user (kandidat) → smart redirect
        if not user._is_public():
            partner = user.partner_id
            return request.redirect(self._get_smart_redirect_url(partner))
        
        # Public user → render halaman dengan snippet
        return request.render('iso17024_portall.pilih_level_page')

    # ---------------------------------------------------------
    # 1. HALAMAN SIGN UP CUSTOM (Dengan Context dari Website)
    # ---------------------------------------------------------
    @http.route('/certification/signup', type='http', auth='public', website=True)
    def custom_signup(self, **kw):
        # Jika user sudah login, cek status registrasi
        if not request.env.user._is_public():
            partner = request.env.user.partner_id
            # Jika pending, lempar ke halaman pending
            if partner.registration_state == 'pending':
                return request.redirect('/certification/pending')
            # Jika approved, lempar ke apply
            elif partner.registration_state == 'approved':
                return request.redirect('/certification/apply')
            # Jika none/rejected tapi sudah login, tetap ke apply
            return request.redirect('/certification/apply')
        
        # Ambil context dari URL params
        cert_type = kw.get('type', 'new')  # 'new' atau 'recert'
        cert_level = kw.get('level', 'level1')  # 'level1' atau 'level2'
            
        return request.render('iso17024_portall.custom_signup_page', {
            'error': kw.get('error'),
            'values': kw,
            'cert_type': cert_type,
            'cert_level': cert_level,
        })

    # ---------------------------------------------------------
    # 2. PROSES SUBMIT SIGN UP (Simpan Context + Set Pending)
    # ---------------------------------------------------------
    @http.route('/certification/signup/submit', type='http', auth='public', methods=['POST'], website=True)
    def custom_signup_submit(self, **kw):
        try:
            login = kw.get('email')
            name = kw.get('name')
            password = kw.get('password')
            confirm = kw.get('confirm_password')
            
            # Ambil pilihan sertifikasi dari form
            cert_type = kw.get('cert_type', 'new')
            cert_level = kw.get('cert_level', 'level1')

            if password != confirm:
                return request.redirect(f'/certification/signup?type={cert_type}&level={cert_level}&error=Password tidak sama')

            # Buat User Baru
            result = request.env['res.users'].sudo().signup({
                'login': login,
                'email': login,
                'name': name,
                'password': password,
            })
            
            # Cari partner yang baru dibuat dan update data registrasi
            user = request.env['res.users'].sudo().search([('login', '=', login)], limit=1)
            if user and user.partner_id:
                user.partner_id.sudo().write({
                    'registration_state': 'pending',
                    'pending_cert_type': cert_type,
                    'pending_cert_level': cert_level,
                    'registration_date': fields.Datetime.now(),
                })
                # Post message
                user.partner_id.sudo().message_post(
                    body=f"<b style='color:blue'>📝 REGISTRASI BARU</b><br/>"
                         f"Jenis: {cert_type}<br/>"
                         f"Level: {cert_level}<br/>"
                         f"Menunggu verifikasi admin."
                )

            # Redirect ke halaman pending PUBLIC (tanpa perlu login)
            # User TIDAK BISA login sampai admin approve
            import urllib.parse
            return request.redirect('/certification/pending?email=%s&name=%s' % (
                urllib.parse.quote(login),
                urllib.parse.quote(name)
            ))

        except Exception as e:
            cert_type = kw.get('cert_type', 'new')
            cert_level = kw.get('cert_level', 'level1')
            return request.redirect(f'/certification/signup?type={cert_type}&level={cert_level}&error=' + str(e))

    # ---------------------------------------------------------
    # 3. HALAMAN PENDING (PUBLIC - Tanpa Login)
    # ---------------------------------------------------------
    @http.route('/certification/pending', type='http', auth='public', website=True)
    def pending_page(self, **kw):
        import urllib.parse
        
        # Jika user sudah login dan approved, redirect ke apply
        if not request.env.user._is_public():
            partner = request.env.user.partner_id
            if partner.registration_state == 'approved':
                return request.redirect('/certification/apply')
        
        # Ambil info dari URL params (untuk user yang baru signup)
        email = urllib.parse.unquote(kw.get('email', ''))
        name = urllib.parse.unquote(kw.get('name', ''))
        
        # Cari partner berdasarkan email jika ada
        partner = None
        if email:
            partner = request.env['res.partner'].sudo().search([('email', '=', email)], limit=1)
        
        return request.render('iso17024_portall.pending_verification_page', {
            'email': email,
            'name': name,
            'partner': partner,
            'user': request.env.user if not request.env.user._is_public() else None,
        })

    # ---------------------------------------------------------
    # 4. OVERRIDE LOGIN - BLOCK PENDING USERS
    # ---------------------------------------------------------
    @http.route('/web/login', type='http', auth="public")
    def web_login(self, redirect=None, **kw):
        # Cek SEBELUM login apakah user ini pending
        login_email = kw.get('login', '')
        if login_email and request.httprequest.method == 'POST':
            # Cari user berdasarkan email
            user = request.env['res.users'].sudo().search([('login', '=', login_email)], limit=1)
            if user and user.partner_id:
                partner = user.partner_id
                # BLOCK login jika status pending
                if partner.registration_state == 'pending':
                    return request.render('web.login', {
                        'error': 'Akun Anda belum diverifikasi oleh Admin. Silakan tunggu email konfirmasi.',
                        'login': login_email,
                    })
                # BLOCK login jika status rejected
                elif partner.registration_state == 'rejected':
                    return request.render('web.login', {
                        'error': 'Pendaftaran Anda ditolak. Silakan hubungi admin untuk informasi lebih lanjut.',
                        'login': login_email,
                    })
        
        # Lanjutkan login normal
        response = super(IsoPortalController, self).web_login(redirect, **kw)

        if request.params.get('login_success'):
            user = request.env.user
            partner = user.partner_id

            # === SESSION TRACKING: Create new session, kick old devices ===
            try:
                request.env['cert.user.session'].sudo().create_session(
                    user_id=user.id,
                    session_token=request.session.sid,
                    ip_address=request.httprequest.remote_addr,
                    user_agent=request.httprequest.user_agent.string if request.httprequest.user_agent else '',
                )
            except Exception as e:
                import logging
                _logger = logging.getLogger(__name__)
                _logger.error(f"Failed to create session tracking: {e}")
            # === END SESSION TRACKING ===

            # Jika BUKAN Internal User (artinya kandidat portal)
            if not user.has_group('base.group_user'):
                # Cek status registrasi - approved bisa lanjut
                if partner.registration_state == 'approved':
                    return request.redirect('/certification/apply')
                # Default untuk none/lainnya → apply (backward compatibility untuk user lama)
                return request.redirect('/certification/apply')

        return response

    # ---------------------------------------------------------
    # 5. HALAMAN STATUS DASHBOARD (SETELAH SUBMIT)
    # ---------------------------------------------------------
    @http.route('/certification/status', type='http', auth='user', website=True)
    def application_status(self, **kw):
        partner = request.env.user.partner_id
        
        # Cek status registrasi dulu
        if partner.registration_state == 'pending':
            return request.redirect('/certification/pending')
        
        app = request.env['certification.application'].search([
            ('partner_id', '=', partner.id)
        ], limit=1)
        
        if not app or app.state == 'draft':
            return request.redirect('/certification/apply')

        # State payment tetap ke status page (tombol bayar Xendit di sana)
        # if app.state == 'payment':
        #     return request.redirect('/certification/payment')
        
        return request.render('iso17024_portall.application_status_page', {
            'application': app,
            'user': request.env.user,
        })

    # ---------------------------------------------------------
    # 6. HALAMAN STEP 1: UPLOAD BERKAS (NEW 2-STEP FLOW)
    # ---------------------------------------------------------
    @http.route('/certification/apply', type='http', auth='user', website=True)
    def certification_wizard(self, **kw):
        partner = request.env.user.partner_id
        
        # Cek status registrasi - harus approved untuk akses
        if partner.registration_state == 'pending':
            return request.redirect('/certification/pending')
        
        app = request.env['certification.application'].search([
            ('partner_id', '=', partner.id)
        ], limit=1)
        
        edit_mode = kw.get('edit')
        
        if app:
            if edit_mode and app.state == 'revision':
                app.sudo().write({'state': 'draft'})
                # Stay on step 1 for revision
            
            if not edit_mode:
                if app.state not in ['draft']:
                    # Semua state kecuali draft → ke status page
                    return request.redirect('/certification/status')
                
                # 2-STEP FLOW: If step >= 2, redirect to step2 (Review)
                if app.current_step >= 2:
                    return request.redirect('/certification/apply/step2')

        # Render Step 1: Upload Berkas
        return request.render('iso17024_portall.application_wizard_page', {
            'application': app,
            'user': request.env.user,
            'partner': partner,
        })
    
    # ---------------------------------------------------------
    # SUBMIT STEP 1: UPLOAD BERKAS (NEW 2-STEP FLOW)
    # ---------------------------------------------------------
    @http.route('/certification/apply/step1/submit', type='http', auth='user', methods=['POST'], website=True)
    def submit_step_1(self, **kw):
        user = request.env.user
        partner = user.partner_id
        
        def get_file_data(field_name):
            file = kw.get(field_name)
            if file and hasattr(file, 'read'):
                return base64.b64encode(file.read())
            return False
        
        # Core data
        vals = {
            'partner_id': partner.id,
            'state': 'draft',
            'current_step': 1,
            # Pre-fill dari pending data
            'application_type': partner.pending_cert_type or 'new',
            'scheme': partner.pending_cert_level or 'level1',
        }
        
        # File uploads mapping
        files_map = {
            'pas_foto': 'pas_foto',
            'ktp_file': 'ktp_file',
            'cv_file': 'cv_file',
            'ijazah_file': 'ijazah_file',
            'training_cert': 'training_cert',
            'cert_level1_file': 'cert_level1_file',
        }

        for input_name, db_field in files_map.items():
            file_data = get_file_data(input_name)
            if file_data:
                vals[db_field] = file_data

        existing_app = request.env['certification.application'].sudo().search([
            ('partner_id', '=', partner.id)
        ], limit=1)

        if existing_app:
            existing_app.sudo().write(vals)
        else:
            request.env['certification.application'].sudo().create(vals)
            
        return request.redirect('/certification/apply/step2')
    
    # ---------------------------------------------------------
    # HALAMAN STEP 2: REVIEW & DECLARATION (NEW 2-STEP FLOW)
    # ---------------------------------------------------------
    @http.route('/certification/apply/step2', type='http', auth='user', website=True)
    def step2_page(self, **kw):
        app = request.env['certification.application'].search([
            ('partner_id', '=', request.env.user.partner_id.id)
        ], limit=1)

        if not app:
            return request.redirect('/certification/apply')

        return request.render('iso17024_portall.application_step2_page', {
            'application': app,
            'partner': request.env.user.partner_id,
        })

    # ---------------------------------------------------------
    # FINAL SUBMIT (STEP 2 - KUNCI DATA)
    # ---------------------------------------------------------
    @http.route('/certification/apply/submit_final', type='http', auth='user', methods=['POST'], website=True)
    def submit_final(self, **kw):
        app = request.env['certification.application'].search([
            ('partner_id', '=', request.env.user.partner_id.id)
        ], limit=1)

        if app:
            app.sudo().write({
                'declaration_color_blind': True if kw.get('declaration_color_blind') == 'on' else False,
                'declaration_healthy': True if kw.get('declaration_healthy') == 'on' else False,
                'declaration_no_phobia': True if kw.get('declaration_no_phobia') == 'on' else False,
                'declaration_english': True if kw.get('declaration_english') == 'on' else False,
                'declaration_truth': True if kw.get('declaration_truth') == 'on' else False,
                'digital_signature': kw.get('digital_signature'),
                'state': 'submitted',
                'current_step': 2,
                'admin_note': False,  # Clear admin note after resubmit
            })
            # Clear revision flags after resubmit
            app.sudo()._clear_revision_flags()
            
        return request.redirect('/certification/status')

    # ---------------------------------------------------------
    # 7. HALAMAN PEMBAYARAN
    # ---------------------------------------------------------
    @http.route('/certification/payment', type='http', auth='user', website=True)
    def payment_page(self, **kw):
        app = request.env['certification.application'].search([
            ('partner_id', '=', request.env.user.partner_id.id)
        ], limit=1)

        if not app or app.state != 'payment':
            return request.redirect('/certification/status')

        prices = {
            'level1': {'base': 7200000, 'admin': 1600000, 'name': 'Coating Inspector Level 1'},
            'level2': {'base': 13600000, 'admin': 1600000, 'name': 'Coating Inspector Level 2'},
        }
        scheme_data = prices.get(app.scheme, {'base': 7200000, 'admin': 1600000, 'name': 'Sertifikasi'})
        
        return request.render('iso17024_portall.payment_page', {
            'application': app,
            'user': request.env.user,
            'scheme_name': scheme_data['name'],
            'base_price': scheme_data['base'],
            'admin_fee': scheme_data['admin'],
            'total_price': scheme_data['base'] + scheme_data['admin'],
        })

    @http.route('/certification/payment/confirm', type='http', auth='user', website=True)
    def payment_confirm(self, **kw):
        app = request.env['certification.application'].search([
            ('partner_id', '=', request.env.user.partner_id.id)
        ], limit=1)

        if app and app.state == 'payment':
            app.sudo().write({
                'payment_status': 'pending',
            })
            app.sudo().message_post(body="<b style='color:blue'>💰 PEMBAYARAN DIKIRIM</b><br/>User telah submit pembayaran. Menunggu konfirmasi admin.")
        
        return request.redirect('/certification/status')

    # ---------------------------------------------------------
    # 8. XENDIT WEBHOOK CALLBACK
    # ---------------------------------------------------------
    @http.route('/xendit/callback', type='json', auth='public', csrf=False, methods=['POST'])
    def xendit_callback(self, **kw):
        """Handle Xendit payment webhook callback"""
        import json
        import logging
        _logger = logging.getLogger(__name__)
        
        try:
            # Get JSON data from request
            data = request.get_json_data()
            _logger.info(f"Xendit callback received: {json.dumps(data)}")
            
            external_id = data.get('external_id', '')
            status = data.get('status', '')
            xendit_id = data.get('id', '')
            
            # Parse application ID from external_id (format: CERT-{id})
            if external_id.startswith('CERT-'):
                app_id = int(external_id.replace('CERT-', ''))
                
                app = request.env['certification.application'].sudo().browse(app_id)
                
                if app.exists():
                    if status == 'PAID':
                        app.write({
                            'xendit_status': 'paid',
                            'payment_status': 'paid',
                            'state': 'verified',
                            'payment_date': fields.Datetime.now(),
                            'payment_method': data.get('payment_method', 'xendit'),
                        })
                        app.message_post(
                            body=f"<b style='color:green'>✅ PEMBAYARAN DITERIMA (Xendit)</b><br/>"
                                 f"ID: {xendit_id}<br/>"
                                 f"Metode: {data.get('payment_method', '-')}"
                        )
                        _logger.info(f"Application {app_id} payment confirmed via Xendit")
                        
                    elif status == 'EXPIRED':
                        app.write({'xendit_status': 'expired'})
                        app.message_post(body="<b style='color:orange'>⏰ INVOICE XENDIT KADALUARSA</b>")
                        
                    elif status == 'FAILED':
                        app.write({'xendit_status': 'failed'})
                        app.message_post(body="<b style='color:red'>❌ PEMBAYARAN GAGAL</b>")
                        
            return {'status': 'ok'}
            
        except Exception as e:
            _logger.error(f"Xendit callback error: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    # ---------------------------------------------------------
    # 9. XENDIT PAYMENT REDIRECT PAGES
    # ---------------------------------------------------------
    @http.route('/certification/payment/success', type='http', auth='public', website=True)
    def payment_success(self, **kw):
        """Redirect page after successful Xendit payment"""
        app_id = kw.get('app_id')
        
        return request.render('iso17024_portall.payment_success_page', {
            'app_id': app_id,
        })
    
    @http.route('/certification/payment/failed', type='http', auth='public', website=True)
    def payment_failed(self, **kw):
        """Redirect page after failed Xendit payment"""
        app_id = kw.get('app_id')
        
        return request.render('iso17024_portall.payment_failed_page', {
            'app_id': app_id,
        })

    # ---------------------------------------------------------
    # 10. QUIZ / EXAM ROUTES
    # ---------------------------------------------------------
    
    @http.route('/certification/quiz/intro/<int:app_id>', type='http', auth='user', website=True)
    def quiz_intro(self, app_id, **kw):
        """Quiz introduction page - show quiz details before starting"""
        from datetime import datetime
        
        app = request.env['certification.application'].sudo().browse(app_id)
        
        # Validasi akses
        if not app.exists() or app.partner_id.id != request.env.user.partner_id.id:
            return request.render('iso17024_portall.quiz_access_denied')
        
        # Cek status harus scheduled
        if app.state != 'scheduled':
            return request.render('iso17024_portall.quiz_access_denied')
        
        # Cek tanggal ujian sudah tiba
        if app.exam_date and app.exam_date > fields.Datetime.now():
            return request.render('iso17024_portall.quiz_access_denied')
        
        # Cek apakah sudah pernah mengerjakan quiz (done)
        existing_attempt = request.env['cert.quiz.attempt'].sudo().search([
            ('application_id', '=', app.id),
            ('state', '=', 'done')
        ], limit=1)
        
        if existing_attempt:
            # Redirect to result page if already done
            return request.redirect(f'/certification/quiz/result/{existing_attempt.id}')
        
        # Cari quiz berdasarkan scheme
        quiz = request.env['cert.quiz'].sudo().search([
            ('scheme', '=', app.scheme),
            ('published', '=', True)
        ], limit=1)
        
        if not quiz:
            return request.render('iso17024_portall.quiz_access_denied')
        
        return request.render('iso17024_portall.quiz_intro_page', {
            'quiz': quiz,
            'application': app,
        })
    
    @http.route('/certification/quiz/start/<int:app_id>', type='http', auth='user', methods=['POST'], website=True)
    def quiz_start(self, app_id, **kw):
        """Start a new quiz attempt"""
        from datetime import datetime
        
        app = request.env['certification.application'].sudo().browse(app_id)
        
        # Validasi akses
        if not app.exists() or app.partner_id.id != request.env.user.partner_id.id:
            return request.render('iso17024_portall.quiz_access_denied')
        
        if app.state != 'scheduled':
            return request.render('iso17024_portall.quiz_access_denied')
        
        # Cek tanggal ujian sudah tiba
        if app.exam_date and app.exam_date > fields.Datetime.now():
            return request.render('iso17024_portall.quiz_access_denied')
        
        # Cek apakah sudah ada attempt in_progress
        existing_attempt = request.env['cert.quiz.attempt'].sudo().search([
            ('application_id', '=', app.id),
            ('state', '=', 'in_progress')
        ], limit=1)
        
        if existing_attempt:
            return request.redirect(f'/certification/quiz/take/{existing_attempt.id}')
        
        # Cek apakah sudah pernah mengerjakan quiz (done)
        done_attempt = request.env['cert.quiz.attempt'].sudo().search([
            ('application_id', '=', app.id),
            ('state', '=', 'done')
        ], limit=1)
        
        if done_attempt:
            return request.redirect(f'/certification/quiz/result/{done_attempt.id}')
        
        # Cari quiz berdasarkan scheme
        quiz = request.env['cert.quiz'].sudo().search([
            ('scheme', '=', app.scheme),
            ('published', '=', True)
        ], limit=1)
        
        if not quiz:
            return request.render('iso17024_portall.quiz_access_denied')
        
        # Create new attempt
        attempt = request.env['cert.quiz.attempt'].sudo().create({
            'application_id': app.id,
            'user_id': request.env.user.id,
            'quiz_id': quiz.id,
        })
        
        return request.redirect(f'/certification/quiz/take/{attempt.id}')
    
    @http.route('/certification/quiz/take/<int:attempt_id>', type='http', auth='user', website=True)
    def quiz_take(self, attempt_id, **kw):
        """Quiz runner page - show questions and timer"""
        attempt = request.env['cert.quiz.attempt'].sudo().browse(attempt_id)

        if not attempt.exists():
            return request.redirect('/certification/status')

        # Validasi user
        if attempt.user_id.id != request.env.user.id:
            return request.render('iso17024_portall.quiz_access_denied')

        # === SESSION VALIDATION: Check if this device is still valid ===
        session_valid = request.env['cert.user.session'].sudo().validate_session(
            user_id=request.env.user.id,
            session_token=request.session.sid
        )
        if not session_valid:
            return request.render('iso17024_portall.session_invalid_page', {
                'attempt': attempt,
            })
        # === END SESSION VALIDATION ===

        # Jika sudah selesai, redirect ke result
        if attempt.state == 'done':
            return request.redirect(f'/certification/quiz/result/{attempt.id}')

        return request.render('iso17024_portall.quiz_runner_page', {
            'attempt': attempt,
            'lines': attempt.answer_line_ids,
        })
    
    @http.route('/certification/quiz/submit/<int:attempt_id>', type='http', auth='user', methods=['POST'], website=True)
    def quiz_submit(self, attempt_id, **post):
        """Submit quiz answers and calculate score"""
        attempt = request.env['cert.quiz.attempt'].sudo().browse(attempt_id)
        
        if not attempt.exists():
            return request.redirect('/certification/status')
        
        # Validasi user
        if attempt.user_id.id != request.env.user.id:
            return request.render('iso17024_portall.quiz_access_denied')
        
        # Jika sudah selesai, redirect ke result
        if attempt.state == 'done':
            return request.redirect(f'/certification/quiz/result/{attempt.id}')
        
        # Simpan jawaban
        for field_name, value in post.items():
            if field_name.startswith('question_'):
                try:
                    line_id = int(field_name.split('_')[1])
                    line = request.env['cert.answer.line'].sudo().browse(line_id)
                    if line.exists() and line.attempt_id.id == attempt.id:
                        line.write({'selected': value})
                except (ValueError, IndexError):
                    continue
        
        # Finish attempt and calculate scores
        attempt.action_finish()
        
        # Update application exam_result based on quiz result
        if attempt.application_id:
            if attempt.is_passed:
                attempt.application_id.sudo().write({'exam_result': 'passed'})
                attempt.application_id.sudo().message_post(
                    body=f"<b style='color:green'>✅ UJIAN LULUS</b><br/>"
                         f"Skor: {attempt.score_percentage:.0f}% ({attempt.score_total}/{attempt.max_score})"
                )
            else:
                attempt.application_id.sudo().write({'exam_result': 'failed'})
                attempt.application_id.sudo().message_post(
                    body=f"<b style='color:red'>❌ UJIAN TIDAK LULUS</b><br/>"
                         f"Skor: {attempt.score_percentage:.0f}% ({attempt.score_total}/{attempt.max_score})<br/>"
                         f"Minimum: {attempt.quiz_id.passing_score}%"
                )
        
        return request.redirect(f'/certification/quiz/result/{attempt.id}')
    
    @http.route('/certification/quiz/result/<int:attempt_id>', type='http', auth='user', website=True)
    def quiz_result(self, attempt_id, **kw):
        """Quiz result page - show score and pass/fail status"""
        attempt = request.env['cert.quiz.attempt'].sudo().browse(attempt_id)

        if not attempt.exists():
            return request.redirect('/certification/status')

        # Validasi user
        if attempt.user_id.id != request.env.user.id:
            return request.render('iso17024_portall.quiz_access_denied')

        return request.render('iso17024_portall.quiz_result_page', {
            'attempt': attempt,
        })

    @http.route('/certification/quiz/check_session', type='json', auth='user', methods=['POST'])
    def quiz_check_session(self, **post):
        """Check if current session is still valid (for multi-device detection)"""
        session_valid = request.env['cert.user.session'].sudo().validate_session(
            user_id=request.env.user.id,
            session_token=request.session.sid
        )
        return {
            'valid': session_valid,
            'message': 'Session aktif' if session_valid else 'Anda telah login dari device lain. Session ini tidak valid lagi.'
        }

    @http.route('/certification/quiz/violation/<int:attempt_id>', type='json', auth='user', methods=['POST'])
    def quiz_violation(self, attempt_id, **post):
        """Log quiz security violation (fullscreen exit, tab switch, etc)"""
        attempt = request.env['cert.quiz.attempt'].sudo().browse(attempt_id)

        if not attempt.exists():
            return {'error': 'Attempt not found'}

        # Validasi user
        if attempt.user_id.id != request.env.user.id:
            return {'error': 'Access denied'}

        # Jika sudah selesai, ignore
        if attempt.state == 'done':
            return {'error': 'Quiz already finished'}

        violation_type = post.get('type', 'unknown')
        result = attempt.log_violation(violation_type)

        # Log to application chatter if this is a penalty or auto_submit
        if result.get('action') in ['penalty', 'auto_submit']:
            attempt.application_id.sudo().message_post(
                body=f"<b style='color:orange'>⚠️ PELANGGARAN KEAMANAN</b><br/>"
                     f"Tipe: {violation_type}<br/>"
                     f"Pelanggaran ke-{result.get('count')}<br/>"
                     f"Total Pengurangan: {result.get('total_penalty')}%"
            )

        return result
