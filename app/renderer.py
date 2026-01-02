import base64
import os
# sys.path hack entfernen
from jinja2 import Environment, BaseLoader
from lxml import etree
from sqlmodel import Session, select
from weasyprint import HTML, Attachment

# Import relativ zum Execution Context
from data import Company, Customer, Invoice, InvoiceItem, engine # <--- "app." entfernt


_TEMPLATE = """
<!doctype html>
<html lang="de">
<head>
    <meta charset="utf-8" />
    <title>{{ invoice.title }} {{ invoice.nr }}</title>
    <style>
        @page { size: A4; margin: 0; }
        body { margin: 0; font-family: Helvetica, Arial, sans-serif; color: #111; }
        .page { position: relative; width: 210mm; height: 297mm; }
        .fold-mark, .hole-mark {
            position: absolute;
            left: 0;
            width: 5mm;
            border-top: 0.2mm solid #111;
        }
        .fold-mark.first { top: 105mm; }
        .fold-mark.second { top: 210mm; }
        .hole-mark { top: 148.5mm; }
        .address-block {
            position: absolute;
            top: 45mm;
            left: 20mm;
            width: 85mm;
            height: 45mm;
            font-size: 10pt;
            line-height: 1.2;
        }
        .return-address {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 5mm;
            font-size: 8pt;
        }
        .recipient {
            position: absolute;
            top: 7mm;
            left: 0;
            right: 0;
        }
        .header {
            position: absolute;
            top: 20mm;
            left: 120mm;
            right: 20mm;
            text-align: right;
            font-size: 9pt;
            line-height: 1.4;
        }
        .meta {
            position: absolute;
            top: 105mm;
            left: 20mm;
            right: 20mm;
            font-size: 10pt;
        }
        .subject {
            margin-top: 10mm;
            font-size: 12pt;
            font-weight: bold;
        }
        .items {
            width: 100%;
            border-collapse: collapse;
            margin-top: 8mm;
            font-size: 9.5pt;
        }
        .items th, .items td {
            border-bottom: 0.2mm solid #ddd;
            padding: 2.5mm 0;
            text-align: left;
        }
        .items th.right, .items td.right { text-align: right; }
        .totals {
            width: 100%;
            margin-top: 6mm;
            font-size: 10pt;
        }
        .totals td { padding: 1mm 0; }
        .totals .label { text-align: right; padding-right: 4mm; }
        .footer {
            position: absolute;
            bottom: 20mm;
            left: 20mm;
            right: 20mm;
            font-size: 8.5pt;
            color: #444;
        }
    </style>
</head>
<body>
    <div class="page">
        <div class="fold-mark first"></div>
        <div class="fold-mark second"></div>
        <div class="hole-mark"></div>

        <div class="address-block">
            <div class="return-address">{{ return_address }}</div>
            <div class="recipient">
                <div>{{ recipient_name }}</div>
                <div>{{ recipient_street }}</div>
                <div>{{ recipient_postal }} {{ recipient_city }}</div>
            </div>
        </div>

        <div class="header">
            <div><strong>{{ company.name }}</strong></div>
            <div>{{ company.first_name }} {{ company.last_name }}</div>
            <div>{{ company.street }}</div>
            <div>{{ company.postal_code }} {{ company.city }}</div>
            {% if company.email %}<div>{{ company.email }}</div>{% endif %}
            {% if company.phone %}<div>{{ company.phone }}</div>{% endif %}
            {% if company.iban %}<div>IBAN: {{ company.iban }}</div>{% endif %}
            {% if company.tax_id %}<div>Steuernummer: {{ company.tax_id }}</div>{% endif %}
            {% if company.vat_id %}<div>USt-IdNr.: {{ company.vat_id }}</div>{% endif %}
        </div>

        <div class="meta">
            <div class="subject">{{ invoice.title }} {{ invoice.nr }}</div>
            <div>Datum: {{ invoice.date }}</div>
            {% if invoice.delivery_date %}<div>Lieferdatum: {{ invoice.delivery_date }}</div>{% endif %}

            <table class="items">
                <thead>
                    <tr>
                        <th>Beschreibung</th>
                        <th class="right">Menge</th>
                        <th class="right">Einzelpreis</th>
                        <th class="right">Gesamt</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in line_items %}
                    <tr>
                        <td>{{ item.description }}</td>
                        <td class="right">{{ "%.2f" | format(item.quantity) }}</td>
                        <td class="right">{{ "%.2f" | format(item.unit_price) }} €</td>
                        <td class="right">{{ "%.2f" | format(item.total) }} €</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>

            <table class="totals">
                <tr>
                    <td class="label">Zwischensumme</td>
                    <td class="right">{{ "%.2f" | format(totals.netto) }} €</td>
                </tr>
                <tr>
                    <td class="label">USt. ({{ "%.0f" | format(totals.tax_rate * 100) }}%)</td>
                    <td class="right">{{ "%.2f" | format(totals.tax_amount) }} €</td>
                </tr>
                <tr>
                    <td class="label"><strong>Gesamt</strong></td>
                    <td class="right"><strong>{{ "%.2f" | format(totals.brutto) }} €</strong></td>
                </tr>
            </table>
        </div>

        <div class="footer">
            {% if totals.tax_rate == 0 %}
            <div>Gemäß § 19 UStG wird keine Umsatzsteuer berechnet.</div>
            {% endif %}
            <div>Vielen Dank für Ihren Auftrag.</div>
        </div>
    </div>
</body>
</html>
"""


def _load_company_customer(invoice: Invoice):
    with Session(engine) as session:
        company = session.exec(select(Company)).first()
        customer = session.get(Customer, invoice.customer_id) if invoice.customer_id else None
    return company, customer


def _collect_line_items(invoice: Invoice):
    preview_items = invoice.__dict__.get('line_items')
    if preview_items is not None:
        return preview_items
    if not invoice.id:
        return []
    with Session(engine) as session:
        return session.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice.id)).all()


def _derive_tax_rate(invoice: Invoice, line_items):
    stored_tax_rate = invoice.__dict__.get('tax_rate')
    if stored_tax_rate is not None:
        return float(stored_tax_rate)
    if invoice.__dict__.get('apply_ustg19'):
        return 0.0
    net_total = 0.0
    for item in line_items:
        if isinstance(item, dict):
            net_total += float(item.get('qty') or 0) * float(item.get('price') or 0)
        else:
            net_total += float(item.quantity or 0) * float(item.unit_price or 0)
    if invoice.total_brutto and net_total > 0:
        rate = (float(invoice.total_brutto) / net_total) - 1
        return max(rate, 0.0)
    return 0.19


def _prepare_items(invoice: Invoice):
    raw_items = _collect_line_items(invoice)
    tax_rate = _derive_tax_rate(invoice, raw_items)
    prepared = []
    net_total = 0.0
    for item in raw_items:
        if isinstance(item, dict):
            desc = item.get('desc') or item.get('description') or ''
            qty = float(item.get('qty') or item.get('quantity') or 0)
            price = float(item.get('price') or item.get('unit_price') or 0)
            is_brutto = bool(item.get('is_brutto') or False)
        else:
            desc = item.description or ''
            qty = float(item.quantity or 0)
            price = float(item.unit_price or 0)
            is_brutto = False
        unit_netto = price
        if tax_rate > 0 and is_brutto:
            unit_netto = price / (1 + tax_rate)
        total = qty * unit_netto
        net_total += total
        prepared.append({
            'description': desc,
            'quantity': qty,
            'unit_price': unit_netto,
            'total': total,
        })
    brutto = float(invoice.total_brutto or 0) or (net_total * (1 + tax_rate))
    tax_amount = brutto - net_total
    return prepared, {'netto': net_total, 'brutto': brutto, 'tax_rate': tax_rate, 'tax_amount': tax_amount}


def _build_zugferd_xml(company, customer, invoice, items, tax_rate):
    netto = sum(item['total'] for item in items)
    brutto = netto * (1 + tax_rate)
    nsmap = {
        'rsm': 'urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100',
        'ram': 'urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100',
        'qdt': 'urn:un:unece:uncefact:data:standard:QualifiedDataType:100',
        'udt': 'urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100',
    }
    root = etree.Element('{%s}CrossIndustryInvoice' % nsmap['rsm'], nsmap=nsmap)
    context = etree.SubElement(root, '{%s}ExchangedDocumentContext' % nsmap['rsm'])
    guideline = etree.SubElement(context, '{%s}GuidelineSpecifiedDocumentContextParameter' % nsmap['ram'])
    etree.SubElement(guideline, '{%s}ID' % nsmap['ram']).text = 'urn:cen.eu:en16931:2017'

    document = etree.SubElement(root, '{%s}ExchangedDocument' % nsmap['rsm'])
    etree.SubElement(document, '{%s}ID' % nsmap['ram']).text = str(invoice.nr or '')
    etree.SubElement(document, '{%s}TypeCode' % nsmap['ram']).text = '380'
    issue_date = etree.SubElement(document, '{%s}IssueDateTime' % nsmap['ram'])
    date_str = (invoice.date or '').replace('-', '')
    date_time = etree.SubElement(issue_date, '{%s}DateTimeString' % nsmap['udt'])
    date_time.set('format', '102')
    date_time.text = date_str

    transaction = etree.SubElement(root, '{%s}SupplyChainTradeTransaction' % nsmap['rsm'])
    agreement = etree.SubElement(transaction, '{%s}ApplicableHeaderTradeAgreement' % nsmap['ram'])
    seller = etree.SubElement(agreement, '{%s}SellerTradeParty' % nsmap['ram'])
    etree.SubElement(seller, '{%s}Name' % nsmap['ram']).text = company.name or ''
    if company.tax_id:
        tax_reg = etree.SubElement(seller, '{%s}SpecifiedTaxRegistration' % nsmap['ram'])
        etree.SubElement(tax_reg, '{%s}ID' % nsmap['ram']).text = company.tax_id
    buyer = etree.SubElement(agreement, '{%s}BuyerTradeParty' % nsmap['ram'])
    buyer_name = customer.display_name if customer else invoice.recipient_name
    etree.SubElement(buyer, '{%s}Name' % nsmap['ram']).text = buyer_name or ''

    delivery = etree.SubElement(transaction, '{%s}ApplicableHeaderTradeDelivery' % nsmap['ram'])
    etree.SubElement(delivery, '{%s}ActualDeliverySupplyChainEvent' % nsmap['ram'])

    settlement = etree.SubElement(transaction, '{%s}ApplicableHeaderTradeSettlement' % nsmap['ram'])
    etree.SubElement(settlement, '{%s}InvoiceCurrencyCode' % nsmap['ram']).text = 'EUR'
    tax = etree.SubElement(settlement, '{%s}ApplicableTradeTax' % nsmap['ram'])
    etree.SubElement(tax, '{%s}TypeCode' % nsmap['ram']).text = 'VAT'
    etree.SubElement(tax, '{%s}CategoryCode' % nsmap['ram']).text = 'S'
    etree.SubElement(tax, '{%s}RateApplicablePercent' % nsmap['ram']).text = f"{tax_rate * 100:.2f}"
    monetary = etree.SubElement(settlement, '{%s}SpecifiedTradeSettlementHeaderMonetarySummation' % nsmap['ram'])
    etree.SubElement(monetary, '{%s}LineTotalAmount' % nsmap['ram']).text = f"{netto:.2f}"
    etree.SubElement(monetary, '{%s}TaxBasisTotalAmount' % nsmap['ram']).text = f"{netto:.2f}"
    etree.SubElement(monetary, '{%s}TaxTotalAmount' % nsmap['ram']).text = f"{netto * tax_rate:.2f}"
    etree.SubElement(monetary, '{%s}GrandTotalAmount' % nsmap['ram']).text = f"{brutto:.2f}"
    etree.SubElement(monetary, '{%s}DuePayableAmount' % nsmap['ram']).text = f"{brutto:.2f}"

    for index, line in enumerate(items, start=1):
        line_item = etree.SubElement(transaction, '{%s}IncludedSupplyChainTradeLineItem' % nsmap['ram'])
        document_line = etree.SubElement(line_item, '{%s}AssociatedDocumentLineDocument' % nsmap['ram'])
        etree.SubElement(document_line, '{%s}LineID' % nsmap['ram']).text = str(index)
        product = etree.SubElement(line_item, '{%s}SpecifiedTradeProduct' % nsmap['ram'])
        etree.SubElement(product, '{%s}Name' % nsmap['ram']).text = line['description']
        agreement_line = etree.SubElement(line_item, '{%s}SpecifiedLineTradeAgreement' % nsmap['ram'])
        gross_price = etree.SubElement(agreement_line, '{%s}GrossPriceProductTradePrice' % nsmap['ram'])
        etree.SubElement(gross_price, '{%s}ChargeAmount' % nsmap['ram']).text = f"{line['unit_price']:.2f}"
        delivery_line = etree.SubElement(line_item, '{%s}SpecifiedLineTradeDelivery' % nsmap['ram'])
        qty = etree.SubElement(delivery_line, '{%s}BilledQuantity' % nsmap['ram'])
        qty.set('unitCode', 'C62')
        qty.text = f"{line['quantity']:.2f}"
        settlement_line = etree.SubElement(line_item, '{%s}SpecifiedLineTradeSettlement' % nsmap['ram'])
        line_tax = etree.SubElement(settlement_line, '{%s}ApplicableTradeTax' % nsmap['ram'])
        etree.SubElement(line_tax, '{%s}TypeCode' % nsmap['ram']).text = 'VAT'
        etree.SubElement(line_tax, '{%s}CategoryCode' % nsmap['ram']).text = 'S'
        etree.SubElement(line_tax, '{%s}RateApplicablePercent' % nsmap['ram']).text = f"{tax_rate * 100:.2f}"
        line_sum = etree.SubElement(settlement_line, '{%s}SpecifiedTradeSettlementLineMonetarySummation' % nsmap['ram'])
        etree.SubElement(line_sum, '{%s}LineTotalAmount' % nsmap['ram']).text = f"{line['total']:.2f}"

    return etree.tostring(root, xml_declaration=True, encoding='utf-8', pretty_print=True)


def render_invoice_to_html(invoice: Invoice, is_preview: bool = False) -> str:
    company, customer = _load_company_customer(invoice)
    line_items, totals = _prepare_items(invoice)
    recipient_name = invoice.recipient_name or (customer.display_name if customer else '')
    recipient_street = invoice.recipient_street or (customer.strasse if customer else '')
    recipient_postal = invoice.recipient_postal_code or (customer.plz if customer else '')
    recipient_city = invoice.recipient_city or (customer.ort if customer else '')
    return_address = f"{company.name} · {company.street} · {company.postal_code} {company.city}" if company else ''

    env = Environment(loader=BaseLoader(), autoescape=True)
    template = env.from_string(_TEMPLATE)
    return template.render(
        invoice=invoice,
        company=company,
        customer=customer,
        line_items=line_items,
        totals=totals,
        recipient_name=recipient_name,
        recipient_street=recipient_street,
        recipient_postal=recipient_postal,
        recipient_city=recipient_city,
        return_address=return_address,
        is_preview=is_preview
    )


def render_invoice_to_pdf_bytes(invoice: Invoice) -> bytes:
    company, customer = _load_company_customer(invoice)
    line_items, totals = _prepare_items(invoice)
    html_content = render_invoice_to_html(invoice)
    zugferd_xml = _build_zugferd_xml(company, customer, invoice, line_items, totals['tax_rate'])
    attachment = Attachment(string=zugferd_xml, filename='factur-x.xml', description='ZUGFeRD 2.x XML', relationship='Alternative')
    return HTML(string=html_content).write_pdf(attachments=[attachment], pdf_variant='pdf/a-3b')


def render_invoice_to_png_base64(invoice: Invoice) -> str:
    html_content = render_invoice_to_html(invoice, is_preview=True)
    png_bytes = HTML(string=html_content).write_png()
    return base64.b64encode(png_bytes).decode('utf-8')
