FROM odoo:19

USER root

# Install qifparse for Accounting QIF Import
RUN pip3 install --no-cache-dir qifparse pdfplumber --break-system-packages

USER odoo
