{
    'name': 'Sales Dynamic Report',
    'version': '1.2',
    'sequence': 1,
    'author': "JD DEVS",
    'category': 'Sales/Sales',
    'depends': ['base', 'sale', 'account', 'purchase', 'stock', 'sale_stock', 'mail', 'web'],
    'data': [
        "security/groups.xml",
    ],
    'assets': {
        'web.assets_backend': [
            "sales_bulk_report/static/src/js/report_button.js",
        ],

        'web.assets_qweb': [
            "sales_bulk_report/static/src/xml/report_button.xml",
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'AGPL-3',
    'images': ['static/description/assets/screenshots/banner.png'],

}
