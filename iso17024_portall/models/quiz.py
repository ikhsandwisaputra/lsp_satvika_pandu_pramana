from odoo import models, fields, api
import random
import logging
import json
from datetime import datetime

_logger = logging.getLogger(__name__)


class CertQuiz(models.Model):
    """Quiz Configuration for Certification Exams"""
    _name = 'cert.quiz'
    _description = 'Kuis Sertifikasi'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Nama Kuis', required=True, tracking=True)
    description = fields.Text(string='Deskripsi')
    
    scheme = fields.Selection([
        ('level1', 'Coating Inspector Level 1'),
        ('level2', 'Coating Inspector Level 2'),
    ], string='Skema Sertifikasi', required=True, tracking=True)
    
    time_limit_minutes = fields.Integer(
        string='Batas Waktu (Menit)', 
        default=60,
        help='Durasi waktu ujian dalam menit'
    )
    passing_score = fields.Float(
        string='Nilai Minimum Lulus (%)', 
        default=70.0,
        help='Persentase minimum untuk dinyatakan lulus'
    )
    
    published = fields.Boolean(string='Published', default=False, tracking=True)
    
    question_ids = fields.One2many('cert.question', 'quiz_id', string='Daftar Soal')
    question_count = fields.Integer(compute='_compute_question_count', string="Total Soal")
    
    attempt_ids = fields.One2many('cert.quiz.attempt', 'quiz_id', string='Percobaan Ujian')
    attempt_count = fields.Integer(compute='_compute_attempt_count', string="Total Percobaan")

    @api.depends('question_ids')
    def _compute_question_count(self):
        for record in self:
            record.question_count = len(record.question_ids)

    @api.depends('attempt_ids')
    def _compute_attempt_count(self):
        for record in self:
            record.attempt_count = len(record.attempt_ids)


class CertQuestion(models.Model):
    """Quiz Question with Multiple Choice Answers"""
    _name = 'cert.question'
    _description = 'Soal Kuis'
    _order = 'sequence, id'

    quiz_id = fields.Many2one('cert.quiz', string='Kuis', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10, help='Urutan soal')
    
    content = fields.Html(string='Pertanyaan', required=True, sanitize=False)
    
    # Pilihan Jawaban A, B, C, D
    choice_a = fields.Char(string='Pilihan A', required=True)
    choice_b = fields.Char(string='Pilihan B', required=True)
    choice_c = fields.Char(string='Pilihan C', required=True)
    choice_d = fields.Char(string='Pilihan D', required=True)
    
    correct_choice = fields.Selection([
        ('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')
    ], string='Jawaban Benar', required=True)
    
    weight = fields.Integer(string='Bobot Nilai', default=1, help='Poin untuk jawaban benar')


class CertQuizAttempt(models.Model):
    """User Quiz Attempt - tracks a single exam session"""
    _name = 'cert.quiz.attempt'
    _description = 'Percobaan Ujian'
    _rec_name = 'display_name'
    _order = 'started_at desc'

    display_name = fields.Char(compute='_compute_display_name', store=True)
    
    application_id = fields.Many2one(
        'certification.application', 
        string='Aplikasi Sertifikasi', 
        required=True, 
        ondelete='cascade'
    )
    user_id = fields.Many2one(
        'res.users', 
        string='Peserta', 
        required=True, 
        default=lambda self: self.env.user
    )
    quiz_id = fields.Many2one('cert.quiz', string='Kuis', required=True)
    
    started_at = fields.Datetime(string='Waktu Mulai', default=fields.Datetime.now)
    finished_at = fields.Datetime(string='Waktu Selesai')
    time_limit_seconds = fields.Integer(string='Batas Waktu (Detik)')
    
    state = fields.Selection([
        ('in_progress', 'Sedang Mengerjakan'),
        ('done', 'Selesai')
    ], string='Status', default='in_progress')
    
    score_total = fields.Float(string='Total Skor', compute='_compute_score', store=True)
    max_score = fields.Float(string='Skor Maksimal', compute='_compute_score', store=True)
    score_percentage = fields.Float(string='Persentase Skor', compute='_compute_score', store=True)
    is_passed = fields.Boolean(string='Lulus?', compute='_compute_score', store=True)
    
    answer_line_ids = fields.One2many('cert.answer.line', 'attempt_id', string='Jawaban')

    # Security tracking fields
    violation_count = fields.Integer(string='Jumlah Pelanggaran', default=0)
    penalty_percentage = fields.Float(string='Pengurangan Nilai (%)', default=0.0)
    security_log = fields.Text(string='Log Keamanan')

    @api.depends('application_id', 'quiz_id', 'started_at')
    def _compute_display_name(self):
        for record in self:
            user_name = record.application_id.partner_id.name or 'Unknown'
            quiz_name = record.quiz_id.name or 'Quiz'
            record.display_name = f"{user_name} - {quiz_name}"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Set time limit from quiz
            if 'quiz_id' in vals:
                quiz = self.env['cert.quiz'].browse(vals['quiz_id'])
                vals['time_limit_seconds'] = quiz.time_limit_minutes * 60
        
        attempts = super().create(vals_list)
        
        for attempt in attempts:
            # Generate answer lines for all questions
            questions = self.env['cert.question'].search([
                ('quiz_id', '=', attempt.quiz_id.id)
            ], order='sequence, id')
            
            # Randomize question order
            questions_list = list(questions)
            random.shuffle(questions_list)
            
            for question in questions_list:
                self.env['cert.answer.line'].create({
                    'attempt_id': attempt.id,
                    'question_id': question.id,
                })
        
        return attempts

    def action_finish(self):
        """Mark the attempt as finished and calculate scores"""
        self.write({
            'state': 'done',
            'finished_at': fields.Datetime.now()
        })
        # Force recompute of scores
        self._compute_score()

    @api.depends('answer_line_ids.score_awarded', 'answer_line_ids.question_id.weight', 'quiz_id.passing_score', 'penalty_percentage')
    def _compute_score(self):
        for record in self:
            total_score = sum(line.score_awarded for line in record.answer_line_ids)
            max_score = sum(line.question_id.weight for line in record.answer_line_ids)

            record.score_total = total_score
            record.max_score = max_score

            if max_score > 0:
                raw_percentage = (total_score / max_score) * 100
                # Apply penalty from security violations
                final_percentage = raw_percentage - record.penalty_percentage
                if final_percentage < 0:
                    final_percentage = 0
                record.score_percentage = final_percentage
                record.is_passed = final_percentage >= (record.quiz_id.passing_score or 70)
            else:
                record.score_percentage = 0
                record.is_passed = False

    def log_violation(self, violation_type):
        """Log security violation and return action to take"""
        self.ensure_one()

        # Increment count
        new_count = self.violation_count + 1

        # Build log entry
        log_entry = {
            'type': violation_type,
            'timestamp': datetime.now().isoformat(),
            'count': new_count
        }

        # Update log
        current_log = json.loads(self.security_log or '[]')
        current_log.append(log_entry)

        # Determine penalty and action
        penalty = 0.0
        action = 'warning'
        message = 'Peringatan! Anda terdeteksi keluar dari mode ujian.'

        if new_count == 2:
            penalty = 10.0
            action = 'penalty'
            message = 'Pelanggaran ke-2! Nilai Anda dikurangi 10%.'
        elif new_count >= 3:
            action = 'auto_submit'
            message = 'Pelanggaran ke-3! Ujian akan otomatis dikumpulkan.'

        self.write({
            'violation_count': new_count,
            'penalty_percentage': self.penalty_percentage + penalty,
            'security_log': json.dumps(current_log)
        })

        return {
            'action': action,
            'count': new_count,
            'total_penalty': self.penalty_percentage,
            'message': message
        }


class CertAnswerLine(models.Model):
    """Individual Answer for a Question"""
    _name = 'cert.answer.line'
    _description = 'Jawaban Peserta'

    attempt_id = fields.Many2one('cert.quiz.attempt', string='Percobaan', ondelete='cascade')
    question_id = fields.Many2one('cert.question', string='Soal', required=True)
    
    selected = fields.Selection([
        ('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')
    ], string='Jawaban Dipilih')
    
    is_correct = fields.Boolean(string='Benar?', compute='_compute_result', store=True)
    score_awarded = fields.Float(string='Skor Didapat', compute='_compute_result', store=True)

    @api.depends('selected', 'question_id', 'question_id.correct_choice', 'question_id.weight')
    def _compute_result(self):
        for line in self:
            if line.selected and line.selected == line.question_id.correct_choice:
                line.is_correct = True
                line.score_awarded = float(line.question_id.weight)
            else:
                line.is_correct = False
                line.score_awarded = 0.0
