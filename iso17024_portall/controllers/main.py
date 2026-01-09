from odoo import http, _
from odoo.http import request
# PERBAIKAN 1: Import dari AuthSignupHome, bukan Home biasa
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
import base64
# PERBAIKAN 2: Warisi AuthSignupHome
class IsoPortalController(AuthSignupHome):

    # ---------------------------------------------------------
    # 1. HALAMAN SIGN UP CUSTOM (Proteksi: User Login DILARANG Masuk)
    # ---------------------------------------------------------
    @http.route('/certification/signup', type='http', auth='public', website=True)
    def custom_signup(self, **kw):
        # Logic: Jika user sudah login (bukan public), lempar ke aplikasi
        if not request.env.user._is_public():
            return request.redirect('/certification/apply')
            
        return request.render('iso17024_portall.custom_signup_page', {
            'error': kw.get('error'),
            'values': kw
        })

    # ---------------------------------------------------------
    # 2. PROSES SUBMIT SIGN UP
    # ---------------------------------------------------------
    @http.route('/certification/signup/submit', type='http', auth='public', methods=['POST'], website=True)
    def custom_signup_submit(self, **kw):
        try:
            login = kw.get('email')
            name = kw.get('name')
            password = kw.get('password')
            confirm = kw.get('confirm_password')

            if password != confirm:
                return request.redirect('/certification/signup?error=Password tidak sama')

            # Buat User Baru
            request.env['res.users'].sudo().signup({
                'login': login,
                'email': login,
                'name': name,
                'password': password,
            })

            # PERBAIKAN 3: Redirect ke Login dengan parameter login
            # Ini aman dan tidak bikin error 500
            return request.redirect('/web/login?login=%s' % login)

        except Exception as e:
            return request.redirect('/certification/signup?error=' + str(e))

    # ---------------------------------------------------------
    # 3. OVERRIDE LOGIN REDIRECT (Logic "Pintu Ajaib")
    # ---------------------------------------------------------
    # PERBAIKAN 4: Gunakan auth='public' (bukan 'none') agar request.env aman
    @http.route('/web/login', type='http', auth="public")
    def web_login(self, redirect=None, **kw):
        # Panggil fungsi asli punya Odoo (super)
        response = super(IsoPortalController, self).web_login(redirect, **kw)
        
        # Cek apakah Login BERHASIL?
        # Odoo otomatis nambahin param 'login_success' kalau password benar
        if request.params.get('login_success'):
            user = request.env.user
            
            # Logic: Jika BUKAN Karyawan (artinya Asesi), lempar ke halaman Apply
            # Kita pakai not has_group('base.group_user') -> group_user adalah Internal User
            if not user.has_group('base.group_user'):
                return request.redirect('/certification/apply')
        
        return response

    # ---------------------------------------------------------
    # 5. HALAMAN STATUS DASHBOARD (SETELAH SUBMIT)
    # ---------------------------------------------------------
    @http.route('/certification/status', type='http', auth='user', website=True)
    def application_status(self, **kw):
        """Halaman status untuk user yang sudah submit aplikasi"""
        app = request.env['certification.application'].search([
            ('partner_id', '=', request.env.user.partner_id.id)
        ], limit=1)
        
        # Jika belum punya aplikasi atau masih draft, redirect ke wizard
        if not app or app.state == 'draft':
            return request.redirect('/certification/apply')
        
        return request.render('iso17024_portall.application_status_page', {
            'application': app,
            'user': request.env.user,
        })

    # ---------------------------------------------------------
    # 6. HALAMAN APLIKASI / WIZARD
    # ---------------------------------------------------------
    @http.route('/certification/apply', type='http', auth='user', website=True)
    def certification_wizard(self, **kw):
        app = request.env['certification.application'].search([
            ('partner_id', '=', request.env.user.partner_id.id)
        ], limit=1)
        
        # Cek apakah user sedang ingin mengedit (mode perbaikan)
        edit_mode = kw.get('edit')
        
        # LOGIC SMART REDIRECT
        if app:
            # Jika dalam mode edit dan status = revision, izinkan edit
            if edit_mode and app.state == 'revision':
                # Reset ke draft agar bisa edit, arahkan ke step terakhir
                app.sudo().write({'state': 'draft'})
                if app.current_step >= 3:
                    return request.redirect('/certification/apply/step3')
                elif app.current_step == 2:
                    return request.redirect('/certification/apply/step2')
            
            # Jika TIDAK dalam edit mode
            if not edit_mode:
                # Status selain draft -> ke halaman Status
                if app.state not in ['draft']:
                    return request.redirect('/certification/status')
                
                # Jika masih draft, arahkan ke step terakhir
                if app.current_step == 2:
                    return request.redirect('/certification/apply/step2')
                elif app.current_step == 3:
                    return request.redirect('/certification/apply/step3')
                elif app.current_step >= 4:
                    return request.redirect('/certification/apply/step4')

        return request.render('iso17024_portall.application_wizard_page', {
            'application': app,
            'user': request.env.user,
        })
    
    # ---------------------------------------------------------
    # SUBMIT STEP 1 (UPDATED)
    # ---------------------------------------------------------
    @http.route('/certification/apply/step1/submit', type='http', auth='user', methods=['POST'], website=True)
    def submit_step_1(self, **kw):
        user = request.env.user
        partner = user.partner_id
        
        vals = {
            'partner_id': partner.id,
            'nik': kw.get('nik'),
            'birth_date': kw.get('birth_date'),
            
            # --- SIMPAN FIELD BARU ---
            'place_of_birth': kw.get('place_of_birth'),
            'last_education': kw.get('last_education'),
            # -------------------------
            
            'phone': kw.get('phone'),
            'address': kw.get('address'),
            'nationality_id': int(kw.get('nationality_id')) if kw.get('nationality_id') else False,
            'special_needs': True if kw.get('special_needs') == 'on' else False,
            'special_needs_desc': kw.get('special_needs_desc'),
            'state': 'draft',
        }
        # Update Nama di User/Partner juga
        if kw.get('name'):
            partner.sudo().write({'name': kw.get('name')})

        # Cek Aplikasi Lama atau Buat Baru
        existing_app = request.env['certification.application'].sudo().search([
            ('partner_id', '=', partner.id)
        ], limit=1)

        if existing_app:
            existing_app.sudo().write(vals)
        else:
            request.env['certification.application'].sudo().create(vals)
            
        # Redirect (Nanti ke Step 2, sementara balik sini dulu dengan pesan sukses)
        # return request.redirect('/certification/apply?saved=1')
        return request.redirect('/certification/apply/step2')
    
    # ---------------------------------------------------------
    # HALAMAN STEP 2: PILIH SKEMA
    # ---------------------------------------------------------
    @http.route('/certification/apply/step2', type='http', auth='user', website=True)
    def step2_page(self, **kw):
        app = request.env['certification.application'].search([
            ('partner_id', '=', request.env.user.partner_id.id)
        ], limit=1)

        if not app:
            return request.redirect('/certification/apply')
            
        # Cek Edit Mode untuk Step 2 juga (jika nanti mundur dari step 3)
        edit_mode = kw.get('edit')
        
        # Jika user sudah di Step 3 tapi buka Step 2 tanpa mode edit -> Lempar ke Step 3
        if app.current_step == 3 and not edit_mode:
             return request.redirect('/certification/apply/step3')

        return request.render('iso17024_portall.application_step2_page', {
            'application': app
        })

    # ---------------------------------------------------------
    # SUBMIT STEP 2
    # ---------------------------------------------------------
    @http.route('/certification/apply/step2/submit', type='http', auth='user', methods=['POST'], website=True)
    def submit_step_2(self, **kw):
        app = request.env['certification.application'].search([
            ('partner_id', '=', request.env.user.partner_id.id)
        ], limit=1)

        if app:
            vals = {
                'application_type': kw.get('application_type'),
                'previous_cert_number': kw.get('previous_cert_number'),
                'scheme': kw.get('scheme'),
                'current_step': 2, # Update progress tracking
            }
            app.sudo().write(vals)

        # Lanjut ke Step 3 (Nanti kita buat)
        # Sementara kita redirect ke halaman yang sama dengan pesan sukses
        # return request.redirect('/certification/apply/step2?saved=1')
        return request.redirect('/certification/apply/step3')
    
    # ---------------------------------------------------------
    # HALAMAN STEP 3: UPLOAD DOKUMEN (INI YANG HILANG)
    # ---------------------------------------------------------
    @http.route('/certification/apply/step3', type='http', auth='user', website=True)
    def step3_page(self, **kw):
        app = request.env['certification.application'].search([
            ('partner_id', '=', request.env.user.partner_id.id)
        ], limit=1)

        # Jika belum ada aplikasi, tendang ke step 1
        if not app:
            return request.redirect('/certification/apply')
            
        # Cek Edit Mode (agar tombol Back dari Step 4 bisa jalan)
        edit_mode = kw.get('edit')
        
        # Jika user sudah selesai (Step 4) tapi buka Step 3 tanpa mode edit -> Lempar ke Step 4
        if app.current_step == 4 and not edit_mode:
             return request.redirect('/certification/apply/step4')

        return request.render('iso17024_portall.application_step3_page', {
            'application': app
        })
    # ---------------------------------------------------------
    # SUBMIT STEP 3 (UPLOAD FILE - UPDATE LENGKAP)
    # ---------------------------------------------------------
    @http.route('/certification/apply/step3/submit', type='http', auth='user', methods=['POST'], website=True)
    def submit_step_3(self, **kw):
        app = request.env['certification.application'].search([
            ('partner_id', '=', request.env.user.partner_id.id)
        ], limit=1)

        if app:
            def get_file_data(field_name):
                file = kw.get(field_name)
                if file and hasattr(file, 'read'):
                    return base64.b64encode(file.read())
                return False

            vals = {'current_step': 3}

            # Mapping Input Name (HTML) -> Database Field (Python)
            files_map = {
                # Dokumen Wajib
                'cv_file': 'cv_file',
                'pas_foto': 'pas_foto',
                'ktp_file': 'ktp_file', # KTP mungkin ada di desain lama, kita simpan saja kalau ada
                'ijazah_file': 'ijazah_file',
                'ishihara_test': 'ishihara_test',
                'skck_file': 'skck_file',
                'training_cert': 'training_cert',
                
                # Dokumen Resertifikasi
                'previous_cert_file': 'previous_cert_file',
                'logbook_file': 'logbook_file',
                
                # Dokumen Level 2 (Sertifikat Level 1 sebagai prasyarat)
                'cert_level1_file': 'cert_level1_file',
                
                # Dokumen Tambahan
                'additional_file': 'additional_file',
            }

            for input_name, db_field in files_map.items():
                file_data = get_file_data(input_name)
                if file_data:
                    vals[db_field] = file_data

            app.sudo().write(vals)

        return request.redirect('/certification/apply/step4')
    
    # ---------------------------------------------------------
    # HALAMAN STEP 4: DECLARATION (FINAL)
    # ---------------------------------------------------------
    @http.route('/certification/apply/step4', type='http', auth='user', website=True)
    def step4_page(self, **kw):
        app = request.env['certification.application'].search([
            ('partner_id', '=', request.env.user.partner_id.id)
        ], limit=1)

        if not app:
            return request.redirect('/certification/apply')

        return request.render('iso17024_portall.application_step4_page', {
            'application': app
        })

    # ---------------------------------------------------------
    # FINAL SUBMIT (KUNCI DATA)
    # ---------------------------------------------------------
    @http.route('/certification/apply/submit_final', type='http', auth='user', methods=['POST'], website=True)
    def submit_final(self, **kw):
        app = request.env['certification.application'].search([
            ('partner_id', '=', request.env.user.partner_id.id)
        ], limit=1)

        if app:
            # Simpan data deklarasi
            app.sudo().write({
                'declaration_compliance': True if kw.get('declaration_compliance') == 'on' else False,
                'declaration_truth': True if kw.get('declaration_truth') == 'on' else False,
                'declaration_liability': True if kw.get('declaration_liability') == 'on' else False,
                'digital_signature': kw.get('digital_signature'),
                
                # Ubah status jadi 'submitted' (Dikunci)
                'state': 'submitted',
                'current_step': 4
            })
            
            # (Opsional) Kirim Email Konfirmasi disini
            
        # Redirect ke Halaman Dashboard/Sukses
        return request.redirect('/certification/apply')