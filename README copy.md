# kubernetes-despacho

despacho

listo

web/database/manager



# para odoo 19 para pruebas

odoo -d tu\_base\_de\_datos -i base --without-demo=all --http-port=8067 --stop-after-init

# Dml-odoo

odoo -i base --without-demo=all --xmlrpc-port=8067 --stop-after-init

odoo -c /etc/odoo/odoo.conf --xmlrpc-port=8067
odoo -i base --xmlrpc-port=8067 --stop-after-init --database=dml

odoo -d odoo16c -u mercadolibre_connector,mercadolibre_payments,mercadolibre_claims,mercadolibre_sales,mercadolibre_reputation,mercadolibre_shipments,mercadolibre_messaging,mercadolibre_products,mercadolibre_label_editor,mercadolibre_billing,billing_portal,ai_agent_core,ai_chatbot_base,ai_activity_pipeline,ai_tools_odoo,ai_playground,impl_paquete_express,mercadolibre_paquete_express --without-demo=all --xmlrpc-port=8067 --stop-after-init


odoo -d odoo17 -u saa\_s\_\_access\_management --without-demo=all --xmlrpc-port=8067 --stop-after-init
odoo -d odoo17 -u licencias\_modulo --without-demo=all --xmlrpc-port=8067 --stop-after-init

Facturacion CFDI
odoo -d odoo18 --xmlrpc-port=8067 --init=

pip install pytesseract --break-system-packages

python odoo-bin -r odoo -w odoo --addons-path=addons -d mydb -i base --without-demo=all



----------postgres
kubectl port-forward service/postgres 5432:5432



configuracion de proxy manager para websockets
location /websocket {
    proxy_pass http://odoo18:8072;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 3600s;
}

location / {
    proxy_pass http://odoo18.default.svc.cluster.local:8069;
}