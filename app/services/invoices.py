from sqlmodel import select

from data import Company, Customer, Invoice, InvoiceItem, InvoiceStatus, get_session
from invoice_numbering import build_invoice_number


# Deprecated: This service is currently unused; keep for backward compatibility.
def finalize_invoice_transaction(company_id, customer_id, invoice_date, total_brutto, items, apply_ustg19, pdf_generator, template_name='', intro_text=''):
    with get_session() as inner:
        with inner.begin():
            company = inner.exec(
                select(Company).where(Company.id == company_id).with_for_update()
            ).first()
            customer = inner.get(Customer, customer_id)
            if not company or not customer:
                raise ValueError('Fehlende Daten')

            invoice = Invoice(
                customer_id=customer.id,
                nr=build_invoice_number(company, customer, company.next_invoice_nr, invoice_date),
                date=invoice_date,
                total_brutto=total_brutto,
                status=InvoiceStatus.OPEN
            )
            inner.add(invoice)
            inner.flush()

            for item in items:
                inner.add(InvoiceItem(
                    invoice_id=invoice.id,
                    description=item.get('desc') or '',
                    quantity=float(item.get('qty') or 0),
                    unit_price=float(item.get('price') or 0)
                ))

            pdf_path = pdf_generator(
                company,
                customer,
                invoice,
                items,
                apply_ustg19=apply_ustg19,
                template_name=template_name,
                intro_text=intro_text
            )
            with open(pdf_path, 'rb') as f:
                invoice.pdf_bytes = f.read()

            company.next_invoice_nr += 1
            inner.add(company)
            inner.add(invoice)

        inner.refresh(invoice)
        inner.refresh(company)
        inner.refresh(customer)

    return company, customer, invoice, pdf_path
