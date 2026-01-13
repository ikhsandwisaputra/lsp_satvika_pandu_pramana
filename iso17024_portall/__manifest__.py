{
    'name': 'ISO 17024 Certification Portal',
    'version': '1.1',
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
        'views/step4_template.xml',
        'views/payment_template.xml',
        'views/status_template.xml',
        'views/backend_views.xml',
        'views/menus.xml',
        # Snippets
        'views/snippets/s_org_structure.xml',
        'views/snippets/s_certification_flow.xml',
        'views/snippets/s_registration_info.xml',
        'views/snippets/s_quality_policy.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'iso17024_portall/static/src/css/snippets.css',
        ],
    },
    'installable': True,
    'application': True,
}