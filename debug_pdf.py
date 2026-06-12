import sys, os
sys.path.insert(0, 'app')
os.environ['DATABASE_URL'] = 'sqlite:///storage/database.db'

from sqlalchemy import text
from db import get_session
from data import Company, Customer, Invoice
from services.invoice_pdf import render_invoice_to_pdf_bytes

with get_session() as s:
    company = s.get(Company, 16)
    print('=== COMPANY DATA ===')
    print(f'  name: {company.name}')
    print(f'  street: {company.street}')
    print(f'  postal_code: {company.postal_code}')
    print(f'  city: {company.city}')
    print(f'  email: {company.email}')
    print(f'  phone: {company.phone}')
    print(f'  bank_name: {company.bank_name}')
    print(f'  iban: {company.iban}')
    print(f'  bic: {company.bic}')
    print(f'  tax_id: {company.tax_id}')
    print(f'  vat_id: {company.vat_id}')
    print(f'  business_type: {company.business_type}')
    print(f'  is_small_business: {company.is_small_business}')

    row = s.exec(text("select id, customer_id from invoice where company_id = 16 and id in (select invoice_id from invoiceitem) limit 1")).first()
    if row:
        invoice_id, cust_id = row
        print(f'\n=== INVOICE {invoice_id} ===')
        customer = s.get(Customer, cust_id)
        print(f'  customer: {customer.name if customer else "None"}')
        invoice = s.get(Invoice, invoice_id)
        pdf = render_invoice_to_pdf_bytes(invoice=invoice, company=company, customer=customer)
    else:
        invoice = s.get(Invoice, 2)
        customer = s.get(Customer, invoice.customer_id) if invoice.customer_id else None
        print(f'\n=== INVOICE {invoice.id} ===')
        print(f'  customer: {customer.name if customer else "None"}')
        pdf = render_invoice_to_pdf_bytes(invoice=invoice, company=company, customer=customer)

    print(f'\n=== PDF GENERATED: {len(pdf)} bytes ===')
    with open('test_output.pdf', 'wb') as f:
        f.write(pdf)
    print('  saved to test_output.pdf')
