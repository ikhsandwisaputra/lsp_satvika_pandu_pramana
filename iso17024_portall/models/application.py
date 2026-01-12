from odoo import models, fields, api

class CertificationApplication(models.Model):
    _name = 'certification.application'
    _description = 'Aplikasi Sertifikasi'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']

    # --- FIELD STEP 1 (DATA DIRI) ---
    nik = fields.Char(string='NIK / Passport', required=True)
    birth_date = fields.Date(string='Tanggal Lahir', required=True)
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
    current_step = fields.Integer(string="Posisi Step Terakhir", default=1, help="1=Data Diri, 2=Skema, 3=Berkas, 4=Done")
    
    is_ktp_valid = fields.Boolean('KTP Valid')
    is_ijazah_valid = fields.Boolean('Ijazah Valid')
    is_ishihara_valid = fields.Boolean('Ishihara Valid')
    
    admin_note = fields.Text('Catatan Admin', help="Isi jika ada dokumen yang perlu diperbaiki")
    # --- TAMBAHAN FIELD SESUAI HTML STEP 3 ---
    cv_file = fields.Binary(string='Daftar Riwayat Hidup (CV)')
    cv_filename = fields.Char(string='Filename CV')
    
    previous_cert_file = fields.Binary(string='File Sertifikat Lama')
    previous_cert_filename = fields.Char(string='Filename Cert Lama')
    
    # Field optional lainnya
    additional_file = fields.Binary(string='Dokumen Tambahan')
    additional_filename = fields.Char(string='Filename Tambahan')

    # --- FIELD STEP 4 (DECLARATION) ---
    declaration_compliance = fields.Boolean('Compliance Agreement')
    declaration_truth = fields.Boolean('Declaration of Truth')
    declaration_liability = fields.Boolean('Liability Release')
    
    # Kita simpan "Tanda Tangan" sebagai Nama yang diketik (Typed Signature)
    # karena Canvas JS butuh file asset terpisah, ini solusi paling stabil untuk XML only.
    digital_signature = fields.Char('Digital Signature Name')
    signature_date = fields.Date('Signature Date', default=fields.Date.today)

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

    # =========================================================
    # TOMBOL AKSI ADMIN
    # =========================================================
    
    def action_verify_documents(self):
        """Admin APPROVE: Dokumen valid, lanjut ke tahap pembayaran"""
        self.write({
            'state': 'payment',
            'admin_note': False,
        })
        self.message_post(body="<b style='color:blue'>waiting for payment</b><br/>Dokumen administrasi valid. Menunggu pembayaran.")

    def action_confirm_payment(self):
        """Admin/System CONFIRM PAYMENT: Sudah bayar, verified"""
        self.write({
            'state': 'verified',
            'payment_status': 'paid',
            'payment_date': fields.Datetime.now(),
            'confirmed_by': self.env.user.id,
        })
        self.message_post(body="<b style='color:green'>✅ PEMBAYARAN DITERIMA</b><br/>Status aplikasi kini Terverifikasi.")

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
        self.write({'state': 'revision'})
        self.message_post(body=f"<b style='color:orange'>⚠️ PERLU REVISI</b><br/>{self.admin_note}")

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