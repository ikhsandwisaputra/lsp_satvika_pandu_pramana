from odoo import models, fields, api
import requests
import base64
import logging
import pytz
from datetime import datetime, time

_logger = logging.getLogger(__name__)

class CertificationApplication(models.Model):
    _name = 'certification.application'
    _description = 'Aplikasi Sertifikasi'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']

    # --- FIELD DATA DIRI (Optional - tidak lagi di-input via form) ---
    nik = fields.Char(string='NIK / Passport')
    birth_date = fields.Date(string='Tanggal Lahir')
    place_of_birth = fields.Char(string='Tempat Lahir')
    last_education = fields.Char(string='Pendidikan Terakhir')
    
    nationality_id = fields.Many2one('res.country', string='Kewarganegaraan')
    phone = fields.Char(string='Nomor Telepon')
    address = fields.Text(string='Alamat Lengkap')
    
    special_needs = fields.Boolean(string='Memiliki Kebutuhan Khusus?')
    special_needs_desc = fields.Text(string='Deskripsi Kebutuhan Khusus')

    partner_id = fields.Many2one('res.partner', string='Kandidat', required=True)
    state = fields.Selection([
        ('draft', 'Draft (Pengisian)'),
        ('submitted', 'Menunggu Verifikasi'),
        ('revision', 'Perlu Revisi'),
        ('payment', 'Menunggu Pembayaran'),
        ('verified', 'Terverifikasi'),
        ('scheduled', 'Terjadwal'),
        ('certified', 'Tersertifikasi'),
        ('rejected', 'Ditolak'),
    ], default='draft', string='Status', tracking=True)

    # --- FIELD STEP 2 (SKEMA) ---
    application_type = fields.Selection([
        ('new', 'Sertifikasi Baru'),
        ('recert', 'Resertifikasi / Perpanjangan')
    ], string='Jenis Permohonan', default='new')
    
    previous_cert_number = fields.Char(string='Nomor Sertifikat Lama')
    
    scheme = fields.Selection([
        ('level1', 'Coating Inspector Level 1'),
        ('level2', 'Coating Inspector Level 2'),
    ], string='Skema Sertifikasi')

    # --- FIELD STEP 3 (DOKUMEN BUKTI) ---
    # 1. Dokumen Dasar
    pas_foto = fields.Binary(string='Pas Foto (4x6 Background Merah)')
    pas_foto_filename = fields.Char(string='Filename Pas Foto')
    
    ktp_file = fields.Binary('File KTP')
    ktp_filename = fields.Char('KTP Filename')
    
    ijazah_file = fields.Binary('Ijazah Terakhir')
    ijazah_filename = fields.Char('Ijazah Filename')
    
    ishihara_test = fields.Binary('Bukti Tes Buta Warna')
    ishihara_filename = fields.Char('Ishihara Filename')
    
    skck_file = fields.Binary(string='SKCK')
    skck_filename = fields.Char(string='Filename SKCK')

    # 2. Dokumen Pendukung
    training_cert = fields.Binary('Sertifikat Pelatihan')
    training_filename = fields.Char('Training Filename')

    # 3. Dokumen Khusus Level 2 (Bukti Level 1)
    cert_level1_file = fields.Binary(string='Sertifikat Level 1 (Untuk Lanjut Level 2)')
    cert_level1_filename = fields.Char(string='Filename Cert L1')

    # 4. Dokumen Khusus Resertifikasi (Logbook)
    logbook_file = fields.Binary(string='Logbook Surveillance 3 Tahun')
    logbook_filename = fields.Char(string='Filename Logbook')

    # --- FIELD TRACKING ADMIN ---
    current_step = fields.Integer(string="Posisi Step Terakhir", default=1, help="1=Upload Berkas, 2=Review/Done")
    
    is_ktp_valid = fields.Boolean('KTP Valid')
    is_ijazah_valid = fields.Boolean('Ijazah Valid')
    is_ishihara_valid = fields.Boolean('Ishihara Valid')
    
    admin_note = fields.Text('Catatan Admin', help="Isi jika ada dokumen yang perlu diperbaiki")
    
    # --- REVISION FLAGS PER DOCUMENT ---
    revision_pas_foto = fields.Boolean('Revisi Pas Foto', default=False)
    revision_ktp = fields.Boolean('Revisi KTP', default=False)
    revision_cv = fields.Boolean('Revisi CV', default=False)
    revision_ijazah = fields.Boolean('Revisi Ijazah', default=False)
    revision_training = fields.Boolean('Revisi Sertifikat Pelatihan', default=False)
    revision_cert_level1 = fields.Boolean('Revisi Sertifikat Level 1', default=False)
    # Khusus Resertifikasi
    revision_previous_cert = fields.Boolean('Revisi Sertifikat Lama', default=False)
    revision_logbook = fields.Boolean('Revisi Logbook', default=False)
    
    # --- DOCUMENT PREVIEW FIELDS (Computed HTML) ---
    preview_pas_foto = fields.Html('Preview Pas Foto', compute='_compute_document_previews', sanitize=False)
    preview_ktp = fields.Html('Preview KTP', compute='_compute_document_previews', sanitize=False)
    preview_cv = fields.Html('Preview CV', compute='_compute_document_previews', sanitize=False)
    preview_ijazah = fields.Html('Preview Ijazah', compute='_compute_document_previews', sanitize=False)
    preview_training = fields.Html('Preview Training Cert', compute='_compute_document_previews', sanitize=False)
    preview_cert_level1 = fields.Html('Preview Cert Level 1', compute='_compute_document_previews', sanitize=False)
    
    @api.depends('pas_foto', 'ktp_file', 'cv_file', 'ijazah_file', 'training_cert', 'cert_level1_file')
    def _compute_document_previews(self):
        """Generate HTML preview for documents"""
        for rec in self:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            
            # Helper for image preview with zoom - using /web/image URL
            def make_image_preview(binary_field, field_name, label):
                if binary_field:
                    # Use Odoo's web/image endpoint for reliable image display
                    image_url = f"{base_url}/web/image/{rec._name}/{rec.id}/{field_name}"
                    return f'''
                        <div style="text-align:center;">
                            <a href="{image_url}" target="_blank">
                                <img src="{image_url}" 
                                     style="max-width:200px; max-height:250px; border:2px solid #e2e8f0; border-radius:8px; cursor:pointer; box-shadow: 0 2px 8px rgba(0,0,0,0.1);"/>
                            </a>
                            <br/><small style="color:#64748b;">📷 {label} - Klik gambar untuk zoom</small>
                        </div>
                    '''
                return '<div style="color:#94a3b8; text-align:center; padding:20px; background:#f8fafc; border-radius:8px;">📭 Belum diupload</div>'
            
            # Helper for PDF/document preview (opens in new tab)
            def make_pdf_preview(binary_field, field_name, filename, label):
                if binary_field:
                    # Create download/view link
                    download_url = f"{base_url}/web/content/{rec._name}/{rec.id}/{field_name}/{filename or 'document.pdf'}?download=false"
                    return f'''
                        <div style="text-align:center; padding:15px; background:#f0f9ff; border-radius:8px; border:1px solid #bae6fd;">
                            <a href="{download_url}" target="_blank" style="text-decoration:none;">
                                <span style="font-size:48px;">📄</span><br/>
                                <span style="color:#0284c7; font-weight:600;">{label}</span><br/>
                                <small style="color:#0369a1;">🔗 Klik untuk preview di tab baru</small>
                            </a>
                        </div>
                    '''
                return '<div style="color:#94a3b8; text-align:center; padding:20px; background:#f8fafc; border-radius:8px;">📭 Belum diupload</div>'
            
            # Generate previews
            rec.preview_pas_foto = make_image_preview(rec.pas_foto, 'pas_foto', 'Pas Foto')
            rec.preview_ktp = make_image_preview(rec.ktp_file, 'ktp_file', 'KTP')
            rec.preview_cv = make_pdf_preview(rec.cv_file, 'cv_file', rec.cv_filename, 'CV / Daftar Riwayat Hidup')
            rec.preview_ijazah = make_pdf_preview(rec.ijazah_file, 'ijazah_file', rec.ijazah_filename, 'Ijazah Terakhir')
            rec.preview_training = make_pdf_preview(rec.training_cert, 'training_cert', rec.training_filename, 'Sertifikat Pelatihan')
            rec.preview_cert_level1 = make_pdf_preview(rec.cert_level1_file, 'cert_level1_file', rec.cert_level1_filename, 'Sertifikat Level 1')
    
    # --- TAMBAHAN FIELD SESUAI HTML STEP 3 ---
    cv_file = fields.Binary(string='Daftar Riwayat Hidup (CV)')
    cv_filename = fields.Char(string='Filename CV')
    
    previous_cert_file = fields.Binary(string='File Sertifikat Lama')
    previous_cert_filename = fields.Char(string='Filename Cert Lama')
    
    # Field optional lainnya
    additional_file = fields.Binary(string='Dokumen Tambahan')
    additional_filename = fields.Char(string='Filename Tambahan')

    # --- FIELD STEP 2 (DECLARATION) ---
    declaration_color_blind = fields.Boolean('Tidak Buta Warna')
    declaration_healthy = fields.Boolean('Berbadan Sehat')
    declaration_no_phobia = fields.Boolean('Tidak Phobia Ketinggian')
    declaration_english = fields.Boolean('Berbahasa Inggris')
    declaration_truth = fields.Boolean('Pernyataan Kebenaran Data')
    
    # Tanda Tangan Digital
    digital_signature = fields.Char('Digital Signature Name')
    signature_date = fields.Date('Signature Date', default=fields.Date.today)

    # --- FIELD INVOICE & XENDIT ---
    invoice_id = fields.Many2one('account.move', string='Invoice', readonly=True, copy=False)
    xendit_invoice_id = fields.Char(string='Xendit Invoice ID', readonly=True, copy=False)
    xendit_payment_url = fields.Char(string='Xendit Payment URL', readonly=True, copy=False)
    xendit_status = fields.Selection([
        ('pending', 'Menunggu Pembayaran'),
        ('paid', 'Sudah Dibayar'),
        ('expired', 'Kadaluarsa'),
        ('failed', 'Gagal'),
    ], string='Status Xendit', readonly=True, copy=False)

    # --- FIELD PEMBAYARAN ---
    payment_amount = fields.Float(string='Jumlah Tagihan', compute='_compute_payment_amount', store=True)
    payment_status = fields.Selection([
        ('unpaid', 'Belum Bayar'),
        ('pending', 'Menunggu Konfirmasi'),
        ('paid', 'Lunas'),
    ], string='Status Pembayaran', default='unpaid', tracking=True)
    payment_date = fields.Datetime(string='Tanggal Pembayaran')
    payment_method = fields.Selection([
        ('va_bca', 'Virtual Account BCA'),
        ('va_mandiri', 'Virtual Account Mandiri'),
        ('va_bni', 'Virtual Account BNI'),
        ('va_bri', 'Virtual Account BRI'),
        ('ewallet', 'E-Wallet'),
        ('qris', 'QRIS'),
        ('manual', 'Transfer Manual'),
    ], string='Metode Pembayaran')
    payment_proof = fields.Binary(string='Bukti Pembayaran')
    payment_proof_filename = fields.Char(string='Filename Bukti')
    payment_note = fields.Text(string='Catatan Pembayaran')
    confirmed_by = fields.Many2one('res.users', string='Dikonfirmasi Oleh')

    # --- FIELD JADWAL ASESMEN ---
    exam_date = fields.Date(string='Tanggal Ujian')
    exam_time = fields.Float(string='Jam Ujian')
    exam_location = fields.Char(string='Lokasi Ujian')
    exam_room = fields.Char(string='Ruangan')
    exam_notes = fields.Text(string='Catatan Tambahan untuk Asesi')
    scheduled_by = fields.Many2one('res.users', string='Dijadwalkan Oleh')
    schedule_date = fields.Datetime(string='Tanggal Penjadwalan')

    # --- FIELD HASIL ASESMEN & SERTIFIKAT ---
    exam_result = fields.Selection([
        ('pending', 'Belum Diumumkan'),
        ('passed', 'Lulus'),
        ('failed', 'Tidak Lulus'),
    ], string='Hasil Asesmen', default='pending', tracking=True)
    
    cert_number = fields.Char(string='Nomor Sertifikat', readonly=True, copy=False)
    cert_issue_date = fields.Date(string='Tanggal Terbit Sertifikat', readonly=True)
    cert_valid_until = fields.Date(string='Berlaku Sampai', compute='_compute_cert_validity', store=True)
    cert_issued_by = fields.Many2one('res.users', string='Diterbitkan Oleh', readonly=True)
    
    is_exam_available = fields.Boolean(compute='_compute_is_exam_available', string='Quiz Available')

    # =========================================================
    # COMPUTE METHODS
    # =========================================================
    
    @api.depends('scheme')
    def _compute_payment_amount(self):
        """Auto-calculate payment amount based on selected scheme"""
        prices = {
            'level1': 8800000,   # Rp 7.200.000 + Rp 1.600.000 (admin)
            'level2': 15200000,  # Rp 13.600.000 + Rp 1.600.000 (admin)
        }
        for rec in self:
            rec.payment_amount = prices.get(rec.scheme, 0)

    @api.depends('cert_issue_date')
    def _compute_cert_validity(self):
        """Auto-calculate certificate validity (3 years from issue date)"""
        from dateutil.relativedelta import relativedelta
        for rec in self:
            if rec.cert_issue_date:
                rec.cert_valid_until = rec.cert_issue_date + relativedelta(years=3)
            else:
                rec.cert_valid_until = False

    def _compute_is_exam_available(self):
        """Check if current time (WIB) is past the exam schedule"""
        tz = pytz.timezone('Asia/Jakarta')
        now_wib = datetime.now(tz)
        
        for rec in self:
            if not rec.exam_date or not rec.payment_status == 'paid' or rec.state not in ['scheduled', 'certified']:
                rec.is_exam_available = False
                continue
                
            # Combine date and time
            # Note: exam_date is Date, exam_time is Float (Hours)
            hours = int(rec.exam_time)
            minutes = int((rec.exam_time - hours) * 60)
            
            # Create scheduled datetime (naive)
            scheduled_naive = datetime.combine(rec.exam_date, time(hours, minutes))
            
            # Localize to WIB
            scheduled_wib = tz.localize(scheduled_naive)
            
            # Allow if current time is >= scheduled time
            rec.is_exam_available = now_wib >= scheduled_wib

    # =========================================================
    # XENDIT INTEGRATION METHODS
    # =========================================================
    
    def _get_xendit_api_key(self):
        """Get Xendit API key from system parameters"""
        return self.env['ir.config_parameter'].sudo().get_param('xendit.api_key', '')
    
    def _get_base_url(self):
        """Get base URL for callbacks"""
        return self.env['ir.config_parameter'].sudo().get_param('web.base.url', 'http://localhost:8019')
    
    def _get_product_by_scheme(self):
        """Find product based on certification scheme"""
        product_name = 'Coating Inspector Level 1' if self.scheme == 'level1' else 'Coating Inspector Level 2'
        product = self.env['product.product'].sudo().search([
            ('name', 'ilike', product_name)
        ], limit=1)
        return product
    
    def _create_invoice(self):
        """Create Odoo invoice for the application"""
        self.ensure_one()
        
        product = self._get_product_by_scheme()
        if not product:
            raise ValueError(f"Produk '{self.scheme}' tidak ditemukan di database!")
        
        # Create invoice
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'product_id': product.id,
                'name': product.name,
                'quantity': 1,
                'price_unit': self.payment_amount,
            })],
        }
        
        invoice = self.env['account.move'].sudo().create(invoice_vals)
        invoice.action_post()  # Validate/post the invoice
        
        self.invoice_id = invoice.id
        return invoice
    
    def _create_xendit_invoice(self):
        """Create invoice on Xendit and get payment URL"""
        self.ensure_one()
        
        api_key = self._get_xendit_api_key()
        if not api_key:
            _logger.warning("Xendit API key not configured!")
            return False
        
        base_url = self._get_base_url()
        
        # Prepare request
        url = "https://api.xendit.co/v2/invoices"
        auth = base64.b64encode(f"{api_key}:".encode()).decode()
        
        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json"
        }
        
        scheme_name = 'Coating Inspector Level 1' if self.scheme == 'level1' else 'Coating Inspector Level 2'
        
        payload = {
            "external_id": f"CERT-{self.id}",
            "amount": int(self.payment_amount),
            "description": f"Biaya Sertifikasi {scheme_name}",
            "invoice_duration": 86400 * 3,  # 3 days
            "customer": {
                "given_names": self.partner_id.name,
                "email": self.partner_id.email or "",
            },
            "success_redirect_url": f"{base_url}/certification/payment/success?app_id={self.id}",
            "failure_redirect_url": f"{base_url}/certification/payment/failed?app_id={self.id}",
            "currency": "IDR",
            "items": [{
                "name": scheme_name,
                "quantity": 1,
                "price": int(self.payment_amount),
            }]
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            self.write({
                'xendit_invoice_id': data.get('id'),
                'xendit_payment_url': data.get('invoice_url'),
                'xendit_status': 'pending',
            })
            
            _logger.info(f"Xendit invoice created: {data.get('id')} for application {self.id}")
            return data
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"Xendit API error: {str(e)}")
            return False
    
    def _send_payment_email(self):
        """Send email to user with payment link"""
        self.ensure_one()
        
        try:
            template = self.env.ref('iso17024_portall.email_template_payment_notification', raise_if_not_found=False)
            if template:
                template.sudo().send_mail(self.id, force_send=True)
                _logger.info(f"Payment email sent to {self.partner_id.email} for application {self.id}")
        except Exception as e:
            _logger.error(f"Failed to send payment email: {str(e)}")

    # =========================================================
    # TOMBOL AKSI ADMIN
    # =========================================================
    
    def action_verify_documents(self):
        """Admin APPROVE: Dokumen valid, create invoice & Xendit payment link"""
        for rec in self:
            # 1. Create Odoo Invoice
            try:
                rec._create_invoice()
            except Exception as e:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error Membuat Invoice!',
                        'message': str(e),
                        'type': 'danger',
                        'sticky': True,
                    }
                }
            
            # 2. Create Xendit Invoice
            xendit_result = rec._create_xendit_invoice()
            
            # 3. Update state
            rec.write({
                'state': 'payment',
                'admin_note': False,
            })
            
            # 4. Post message
            if xendit_result and rec.xendit_payment_url:
                rec.message_post(
                    body=f"<b style='color:blue'>💳 MENUNGGU PEMBAYARAN</b><br/>"
                         f"Dokumen valid. Invoice telah dibuat.<br/>"
                         f"<a href='{rec.xendit_payment_url}' target='_blank'>Klik untuk bayar via Xendit</a>"
                )
            else:
                rec.message_post(
                    body="<b style='color:blue'>💳 MENUNGGU PEMBAYARAN</b><br/>"
                         "Dokumen valid. Invoice telah dibuat.<br/>"
                         "<span style='color:orange'>⚠️ Xendit payment link gagal dibuat. Silakan cek konfigurasi API.</span>"
                )
            
            # 5. Send email
            rec._send_payment_email()

    def action_confirm_payment(self):
        """Admin/System CONFIRM PAYMENT: Sudah bayar, verified"""
        self.write({
            'state': 'verified',
            'payment_status': 'paid',
            'xendit_status': 'paid',
            'payment_date': fields.Datetime.now(),
            'confirmed_by': self.env.user.id,
        })
        
        # Update invoice as paid if exists
        if self.invoice_id and self.invoice_id.state == 'posted':
            # For simplicity, just post a message. Full reconciliation requires payment journal.
            self.invoice_id.message_post(body="Pembayaran dikonfirmasi via Xendit")
        
        self.message_post(body="<b style='color:green'>✅ PEMBAYARAN DITERIMA</b><br/>Status aplikasi kini Terverifikasi.")

    def action_set_schedule(self):
        """Admin SET SCHEDULE: Menjadwalkan ujian asesi setelah pembayaran dikonfirmasi"""
        if not self.exam_date or not self.exam_time or not self.exam_location:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Data Jadwal Wajib Diisi!',
                    'message': 'Silakan isi Tanggal Ujian dan Lokasi Ujian terlebih dahulu.',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        self.write({
            'state': 'scheduled',
            'scheduled_by': self.env.user.id,
        })
        
        # Format time string
        hours = int(self.exam_time)
        minutes = int((self.exam_time - hours) * 60)
        time_str = f"{hours:02d}:{minutes:02d}"
        
        self.message_post(body=f"<b style='color:purple'>📅 UJIAN DIJADWALKAN</b><br/>Tanggal: {self.exam_date} Pukul {time_str}<br/>Lokasi: {self.exam_location}")

    def action_request_revision(self):
        """Admin MINTA REVISI: Ada dokumen yang perlu diperbaiki"""
        if not self.admin_note:
            # Jika admin belum isi catatan, tampilkan warning
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Catatan Wajib Diisi!',
                    'message': 'Silakan isi field "Catatan Admin" terlebih dahulu untuk menjelaskan apa yang perlu diperbaiki.',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        # Cek apakah ada minimal satu dokumen yang dicentang untuk revisi
        has_revision = any([
            self.revision_pas_foto,
            self.revision_ktp,
            self.revision_cv,
            self.revision_ijazah,
            self.revision_training,
            self.revision_cert_level1,
            self.revision_previous_cert,
            self.revision_logbook,
        ])
        
        if not has_revision:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Pilih Dokumen yang Perlu Direvisi!',
                    'message': 'Silakan centang minimal satu dokumen yang perlu diperbaiki oleh asesi.',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        self.write({'state': 'revision'})
        self._send_revision_email()
        self.message_post(body=f"<b style='color:orange'>⚠️ PERLU REVISI</b><br/>{self.admin_note}")
    
    def _send_revision_email(self):
        """Kirim email ke user dengan detail dokumen yang perlu direvisi"""
        try:
            template = self.env.ref('iso17024_portall.email_template_revision_notification', raise_if_not_found=False)
            if template:
                template.sudo().send_mail(self.id, force_send=True)
                _logger.info(f"Revision email sent to {self.partner_id.email} for application {self.id}")
        except Exception as e:
            _logger.error(f"Failed to send revision email: {str(e)}")
    
    def _clear_revision_flags(self):
        """Reset semua flag revisi setelah user submit ulang"""
        self.write({
            'revision_pas_foto': False,
            'revision_ktp': False,
            'revision_cv': False,
            'revision_ijazah': False,
            'revision_training': False,
            'revision_cert_level1': False,
            'revision_previous_cert': False,
            'revision_logbook': False,
        })

    def action_reject(self):
        """Admin TOLAK: Aplikasi ditolak permanen"""
        if not self.admin_note:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Alasan Wajib Diisi!',
                    'message': 'Silakan isi field "Catatan Admin" dengan alasan penolakan.',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        self.write({'state': 'rejected'})
        self.message_post(body=f"<b style='color:red'>❌ DITOLAK</b><br/>{self.admin_note}")

    def action_mark_passed(self):
        """Admin nyatakan LULUS asesmen"""
        self.write({'exam_result': 'passed'})
        self.message_post(body="<b style='color:green'>✅ DINYATAKAN LULUS</b><br/>Asesi telah lulus asesmen. Sertifikat dapat diterbitkan.")

    def action_mark_failed(self):
        """Admin nyatakan TIDAK LULUS asesmen"""
        if not self.admin_note:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Catatan Wajib Diisi!',
                    'message': 'Silakan isi field "Catatan Admin" dengan alasan tidak lulus.',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        self.write({'exam_result': 'failed'})
        self.message_post(body=f"<b style='color:red'>❌ TIDAK LULUS</b><br/>{self.admin_note}")

    def _generate_cert_number(self):
        """
        Certificate number sama dengan registration code dari partner:
        SVK-CIG01-0001-YYMMDD
        """
        # Nomor sertifikat = nomor registrasi
        return self.partner_id.registration_code or f"SVK-CIG0{1 if self.scheme == 'level1' else 2}-TEMP-{self.id}"

    def action_issue_certificate(self):
        """Admin terbitkan sertifikat untuk asesi yang LULUS"""
        for rec in self:
            if rec.exam_result != 'passed':
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Tidak Bisa Terbitkan!',
                        'message': 'Hanya asesi yang LULUS yang dapat diterbitkan sertifikatnya.',
                        'type': 'warning',
                        'sticky': False,
                    }
                }
            
            rec.write({
                'cert_number': rec._generate_cert_number(),
                'cert_issue_date': fields.Date.today(),
                'cert_issued_by': self.env.user.id,
                'state': 'certified',
            })
            
            rec.message_post(
                body=f"<b style='color:purple'>🏆 SERTIFIKAT DITERBITKAN</b><br/>"
                     f"Nomor: <b>{rec.cert_number}</b><br/>"
                     f"Berlaku: {rec.cert_issue_date} s/d {rec.cert_valid_until}"
            )

    def action_reset_quiz(self):
        """Admin reset quiz untuk mengizinkan peserta ujian ulang"""
        for rec in self:
            # Cari semua attempt untuk aplikasi ini
            attempts = self.env['cert.quiz.attempt'].sudo().search([
                ('application_id', '=', rec.id)
            ])

            if not attempts:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Tidak Ada Data Quiz!',
                        'message': 'Peserta belum pernah mengikuti ujian quiz.',
                        'type': 'warning',
                        'sticky': False,
                    }
                }

            # Hapus semua attempt (answer_line_ids akan terhapus via cascade)
            attempts.unlink()

            # Reset exam_result ke pending
            rec.write({'exam_result': 'pending'})

            # Log di chatter
            rec.message_post(
                body=f"<b style='color:blue'>🔄 QUIZ DI-RESET</b><br/>"
                     f"Admin ({self.env.user.name}) telah me-reset ujian quiz.<br/>"
                     f"Peserta dapat mengikuti ujian ulang."
            )