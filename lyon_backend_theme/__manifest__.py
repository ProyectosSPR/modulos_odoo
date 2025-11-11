# -*- coding: utf-8 -*-
{
    "name": "Theme Lyon",
    "summary": "Backend theme, Enterprise, responsive theme",
    "version": "16.0.1",
    "category": "Themes/Backend",
    "license": "OPL-1",
    "support": "relief.4technologies@gmail.com",  
    "author" : "Relief Technologies",    
    "depends": ["base", "web", "mail"],   
    "data": [
        #  "views/res_users.xml", 
         "views/web.xml"
    ],
    "assets": {
        "web.assets_frontend": [
            "/lyon_backend_theme/static/src/css/login.scss",
        ],
        "web.assets_backend": [
            'lyon_backend_theme/static/src/xml/dark_mode.xml',
            'lyon_backend_theme/static/src/xml/systray_dark_mode_menu.xml',
            # 'lyon_backend_theme/views/res_users.xml',
            # 'lyon_backend_theme/views/web.xml',
            "lyon_backend_theme/static/src/css/style.scss",
            'lyon_backend_theme/static/src/components/**/*.xml',
            'lyon_backend_theme/static/src/components/**/*.scss',
            'lyon_backend_theme/static/src/components/ui_context.esm.js',   
            'lyon_backend_theme/static/src/components/**/*.js',            
            'lyon_backend_theme/static/src/js/systray_dark_mode_menu.js',
            "lyon_backend_theme/static/src/css/dark_mode.scss",
        ],       
        
    },
    'images': [
        'static/description/banner.png',
        'static/description/theme_screenshot.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    "price": 36,
    "currency": "EUR"
}
