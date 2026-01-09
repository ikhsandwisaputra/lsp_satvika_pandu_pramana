from odoo import models, fields

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
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('verified', 'Verified'),
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
    # --- TOMBOL AKSI ADMIN ---
    def action_verify_documents(self):
        """Admin klik ini jika semua berkas OK"""
        self.write({'state': 'verified'})
        self.message_post(body="Selamat! Dokumen administrasi Anda telah terverifikasi. Silakan menunggu jadwal ujian.")

    def action_request_revision(self):
        """Admin klik ini jika ada yang salah"""
        self.write({'state': 'draft'}) 
        self.message_post(body=f"PERBAIKAN DOKUMEN: {self.admin_note}")