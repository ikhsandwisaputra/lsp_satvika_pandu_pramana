{
    'name': 'ISO 17024 Certification Portal',
    'version': '1.0',
    'summary': 'Portal Pendaftaran Sertifikasi Coating (Benchmark AMPP)',
    'author': 'User Odoo',
    'category': 'Website',
    'depends': ['website', 'auth_signup', 'portal'],
    'data': [
        'security/ir.model.access.csv',
        'views/signup_template.xml',
        'views/application_template.xml',
        'views/step2_template.xml',
        'views/step3_template.xml',
        'views/step4_template.xml',  # <--- DITAMBAHKAN: Template untuk Step 3
        'views/backend_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
}