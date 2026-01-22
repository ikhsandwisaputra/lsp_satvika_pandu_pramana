from odoo import models, fields, api

class ResPartnerRegistration(models.Model):
    _inherit = 'res.partner'

    # ========================================
    # CANDIDATE REGISTRATION FIELDS
    # ========================================
    
    registration_state = fields.Selection([
        ('none', 'Bukan Kandidat'),
        ('pending', 'Menunggu Verifikasi'),
        ('approved', 'Terverifikasi'),
        ('rejected', 'Ditolak'),
    ], string='Status Registrasi', default='none', tracking=True)
    
    registration_code = fields.Char(
        string='Kode Registrasi', 
        readonly=True, 
        copy=False,
        help='Kode unik yang di-generate saat admin approve registrasi'
    )
    
    # Menyimpan pilihan sertifikasi dari website (sebelum difinalisasi di application)
    pending_cert_type = fields.Selection([
        ('new', 'Sertifikasi Baru'),
        ('recert', 'Resertifikasi'),
    ], string='Jenis Sertifikasi (Pending)')
    
    pending_cert_level = fields.Selection([
        ('level1', 'Coating Inspector Level 1'),
        ('level2', 'Coating Inspector Level 2'),
    ], string='Level Sertifikasi (Pending)')
    
    registration_date = fields.Datetime(
        string='Tanggal Registrasi',
        readonly=True
    )
    
    registration_note = fields.Text(
        string='Catatan Admin',
        help='Catatan dari admin untuk kandidat (jika ada revisi/penolakan)'
    )
    
    approved_by = fields.Many2one(
        'res.users', 
        string='Disetujui Oleh',
        readonly=True
    )
    
    approved_date = fields.Datetime(
        string='Tanggal Persetujuan',
        readonly=True
    )

    # ========================================
    # SEQUENCE FOR REGISTRATION CODE
    # ========================================
    
    def _generate_registration_code(self):
        """
        Generate unique registration code: SVK-CIG01-0001-YYMMDD
        - SVK = Nama LSP (Satvika)
        - CIG01/CIG02 = Coating Inspector Grade 01/02
        - 0001 = Nomor urut per level (auto increment)
        - YYMMDD = Tanggal pendaftaran
        """
        today = fields.Date.today()
        date_str = today.strftime('%y%m%d')  # YYMMDD
        
        # Determine level code
        level = self.pending_cert_level or 'level1'
        level_code = 'CIG01' if level == 'level1' else 'CIG02'
        
        # Get sequence for specific level
        seq_code = f'candidate.registration.{level}'
        sequence = self.env['ir.sequence'].sudo().next_by_code(seq_code)
        
        if not sequence:
            # Fallback: count existing registrations with same level
            count = self.env['res.partner'].sudo().search_count([
                ('registration_code', 'like', f'SVK-{level_code}-%'),
            ])
            sequence = str(count + 1).zfill(4)
        
        return f"SVK-{level_code}-{sequence}-{date_str}"

    # ========================================
    # ADMIN ACTIONS
    # ========================================
    
    def action_approve_registration(self):
        """Admin approves candidate registration"""
        for partner in self:
            if partner.registration_state == 'pending':
                partner.write({
                    'registration_state': 'approved',
                    'registration_code': partner._generate_registration_code(),
                    'approved_by': self.env.user.id,
                    'approved_date': fields.Datetime.now(),
                })
                # Log message
                partner.message_post(
                    body=f"<b style='color:green'>✅ REGISTRASI DISETUJUI</b><br/>"
                         f"Kode Registrasi: <b>{partner.registration_code}</b><br/>"
                         f"Disetujui oleh: {self.env.user.name}"
                )
                
                # Send email notification
                try:
                    template = self.env.ref('iso17024_portall.email_template_registration_approved', raise_if_not_found=False)
                    if template:
                        template.sudo().send_mail(partner.id, force_send=True)
                except Exception as e:
                    # Log error but don't fail the approval
                    partner.message_post(
                        body=f"<b style='color:orange'>⚠️ Email gagal dikirim:</b> {str(e)}"
                    )
    
    def action_reject_registration(self):
        """Admin rejects candidate registration"""
        for partner in self:
            if partner.registration_state == 'pending':
                if not partner.registration_note:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Catatan Wajib Diisi!',
                            'message': 'Silakan isi field "Catatan Admin" dengan alasan penolakan.',
                            'type': 'warning',
                            'sticky': False,
                        }
                    }
                partner.write({
                    'registration_state': 'rejected',
                })
                partner.message_post(
                    body=f"<b style='color:red'>❌ REGISTRASI DITOLAK</b><br/>"
                         f"Alasan: {partner.registration_note}"
                )
