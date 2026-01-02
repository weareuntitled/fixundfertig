import base64
import os
import platform
import ctypes

# -------------------------------------------------------------------------
# 🚑 MACOS LIBRARY FIX (WeasyPrint / GObject / Pango)
# -------------------------------------------------------------------------
# Auf macOS (insb. Apple Silicon) findet Python oft die Homebrew-Bibliotheken nicht.
# Wir laden sie hier explizit vor, damit WeasyPrint sie nutzen kann.
if platform.system() == 'Darwin':
    try:
        # Mögliche Pfade für Homebrew (Apple Silicon vs Intel)
        search_paths = ['/opt/homebrew/lib', '/usr/local/lib']
        
        # Liste der benötigten Bibliotheken mit möglichen Dateinamen
        libs_to_load = [
            # Name, [Liste möglicher Dateinamen]
            ('glib-2.0', ['libglib-2.0.0.dylib', 'libglib-2.0.dylib']),
            ('gobject-2.0', ['libgobject-2.0.0.dylib', 'libgobject-2.0.dylib']),
            ('pango-1.0', ['libpango-1.0.0.dylib', 'libpango-1.0.dylib']),
            ('harfbuzz', ['libharfbuzz.0.dylib', 'libharfbuzz.dylib']),
            ('fontconfig', ['libfontconfig.1.dylib', 'libfontconfig.dylib']),
            ('pangoft2-1.0', ['libpangoft2-1.0.0.dylib', 'libpangoft2-1.0.dylib'])
        ]

        for lib_name, filenames in libs_to_load:
            loaded = False
            for path in search_paths:
                if loaded: break
                for filename in filenames:
                    full_path = os.path.join(path, filename)
                    if os.path.exists(full_path):
                        try:
                            # RTLD_GLOBAL macht die Symbole für nachfolgende Imports (WeasyPrint) sichtbar
                            ctypes.CDLL(full_path, mode=ctypes.RTLD_GLOBAL)
                            loaded = True
                            # print(f"✅ Loaded {lib_name} from {full_path}") # Debug
                            break
                        except OSError:
                            continue
    except Exception as e:
        print(f"⚠️ Warning: macOS DLL loading fix failed: {e}")
# -------------------------------------------------------------------------

from jinja2 import Environment, BaseLoader
from lxml import etree
from sqlmodel import Session, select
from weasyprint import HTML, Attachment

from data import Company, Customer, Invoice, InvoiceItem, engine


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
            text-decoration: underline;
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
            border-top: 1px solid #eee;
            padding-top: 2mm;
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
            {% if company.tax_id %}<div>St-Nr: {{ company.tax_id }}</div>{% endif %}
            {% if company.vat_id %}<div>USt-IdNr: {{ company.vat_id }}</div>{% endif %}
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
            <div>Vielen Dank für Ihren Auftrag. Zahlbar sofort ohne Abzug.</div>
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
    # Check if Invoice model has 'apply_ustg19' logic or similar, defaulting to 19%
    # For now, we assume simple logic: if items imply tax, or default.
    # In a real scenario, this flag should be stored on the invoice.
    # We fallback to standard 19% unless logic says otherwise.
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
            is_brutto = False # Assume net in DB for simplicity or need field
        
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
    
    # Correction for tiny floating point diffs if total_brutto is fixed
    return prepared, {'netto': net_total, 'brutto': brutto, 'tax_rate': tax_rate, 'tax_amount': tax_amount}


def _build_zugferd_xml(company, customer, invoice, items, tax_rate):
    netto = sum(item['total'] for item in items)
    brutto = netto * (1 + tax_rate)
    
    # Basic Namespaces
    nsmap = {
        'rsm': 'urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100',
        'ram': 'urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100',
        'qdt': 'urn:un:unece:uncefact:data:standard:QualifiedDataType:100',
        'udt': 'urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100',
    }
    
    # Root
    root = etree.Element('{%s}CrossIndustryInvoice' % nsmap['rsm'], nsmap=nsmap)
    
    # 1. Context
    context = etree.SubElement(root, '{%s}ExchangedDocumentContext' % nsmap['rsm'])
    guideline = etree.SubElement(context, '{%s}GuidelineSpecifiedDocumentContextParameter' % nsmap['ram'])
    # Factur-X Basic Profile ID
    etree.SubElement(guideline, '{%s}ID' % nsmap['ram']).text = 'urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:basic'

    # 2. Header
    header = etree.SubElement(root, '{%s}ExchangedDocument' % nsmap['rsm'])
    etree.SubElement(header, '{%s}ID' % nsmap['ram']).text = str(invoice.nr or 'DRAFT')
    etree.SubElement(header, '{%s}TypeCode' % nsmap['ram']).text = '380' # 380 = Commercial Invoice
    
    issue_date = etree.SubElement(header, '{%s}IssueDateTime' % nsmap['ram'])
    date_str = (invoice.date or '').replace('-', '') # YYYYMMDD
    date_node = etree.SubElement(issue_date, '{%s}DateTimeString' % nsmap['udt'])
    date_node.set('format', '102') # 102 = YYYYMMDD
    date_node.text = date_str

    # 3. Transaction
    transaction = etree.SubElement(root, '{%s}SupplyChainTradeTransaction' % nsmap['rsm'])
    
    # 3.1 Agreement (Seller/Buyer)
    agreement = etree.SubElement(transaction, '{%s}ApplicableHeaderTradeAgreement' % nsmap['ram'])
    
    # Seller
    seller = etree.SubElement(agreement, '{%s}SellerTradeParty' % nsmap['ram'])
    etree.SubElement(seller, '{%s}Name' % nsmap['ram']).text = company.name or 'Unknown Seller'
    if company.tax_id:
        tax_reg = etree.SubElement(seller, '{%s}SpecifiedTaxRegistration' % nsmap['ram'])
        etree.SubElement(tax_reg, '{%s}ID' % nsmap['ram'], schemeID='FC').text = company.tax_id
    if company.vat_id:
        vat_reg = etree.SubElement(seller, '{%s}SpecifiedTaxRegistration' % nsmap['ram'])
        etree.SubElement(vat_reg, '{%s}ID' % nsmap['ram'], schemeID='VA').text = company.vat_id

    # Buyer
    buyer = etree.SubElement(agreement, '{%s}BuyerTradeParty' % nsmap['ram'])
    etree.SubElement(buyer, '{%s}Name' % nsmap['ram']).text = (customer.display_name if customer else invoice.recipient_name) or 'Unknown Buyer'
    
    # 3.2 Delivery
    delivery = etree.SubElement(transaction, '{%s}ApplicableHeaderTradeDelivery' % nsmap['ram'])
    # Actual delivery date
    if invoice.delivery_date:
        event = etree.SubElement(delivery, '{%s}ActualDeliverySupplyChainEvent' % nsmap['ram'])
        occ_date = etree.SubElement(event, '{%s}OccurrenceDateTime' % nsmap['ram'])
        occ_date_node = etree.SubElement(occ_date, '{%s}DateTimeString' % nsmap['udt'])
        occ_date_node.set('format', '102')
        occ_date_node.text = invoice.delivery_date.replace('-', '')

    # 3.3 Settlement (Payment/Tax)
    settlement = etree.SubElement(transaction, '{%s}ApplicableHeaderTradeSettlement' % nsmap['ram'])
    etree.SubElement(settlement, '{%s}InvoiceCurrencyCode' % nsmap['ram']).text = 'EUR'
    
    # Tax Summary
    tax = etree.SubElement(settlement, '{%s}ApplicableTradeTax' % nsmap['ram'])
    etree.SubElement(tax, '{%s}CalculatedAmount' % nsmap['ram']).text = f"{netto * tax_rate:.2f}"
    etree.SubElement(tax, '{%s}TypeCode' % nsmap['ram']).text = 'VAT'
    etree.SubElement(tax, '{%s}BasisAmount' % nsmap['ram']).text = f"{netto:.2f}"
    etree.SubElement(tax, '{%s}CategoryCode' % nsmap['ram']).text = 'S' # S = Standard
    etree.SubElement(tax, '{%s}RateApplicablePercent' % nsmap['ram']).text = f"{tax_rate * 100:.2f}"

    # Monetary Summation
    monetary = etree.SubElement(settlement, '{%s}SpecifiedTradeSettlementHeaderMonetarySummation' % nsmap['ram'])
    etree.SubElement(monetary, '{%s}LineTotalAmount' % nsmap['ram']).text = f"{netto:.2f}"
    etree.SubElement(monetary, '{%s}TaxBasisTotalAmount' % nsmap['ram']).text = f"{netto:.2f}"
    etree.SubElement(monetary, '{%s}TaxTotalAmount' % nsmap['ram']).text = f"{netto * tax_rate:.2f}" # Total Tax
    etree.SubElement(monetary, '{%s}GrandTotalAmount' % nsmap['ram']).text = f"{brutto:.2f}"
    etree.SubElement(monetary, '{%s}DuePayableAmount' % nsmap['ram']).text = f"{brutto:.2f}"

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
    
    # 1. Render Visual PDF (HTML)
    html_content = render_invoice_to_html(invoice)
    
    # 2. Generate ZUGFeRD XML
    zugferd_xml = _build_zugferd_xml(company, customer, invoice, line_items, totals['tax_rate'])
    
    # 3. Attach XML to PDF
    attachment = Attachment(string=zugferd_xml, filename='factur-x.xml', description='ZUGFeRD 2.x XML', relationship='Alternative')
    
    # 4. Generate PDF/A-3
    return HTML(string=html_content).write_pdf(attachments=[attachment], pdf_variant='pdf/a-3b')


def render_invoice_to_png_base64(invoice: Invoice) -> str:
    # Previews don't need PDF/A or XML attachments, just the look.
    html_content = render_invoice_to_html(invoice, is_preview=True)
    png_bytes = HTML(string=html_content).write_png()
    return base64.b64encode(png_bytes).decode('utf-8')