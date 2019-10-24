# -*- coding: utf-8 -*-
from odoo import http, SUPERUSER_ID
from odoo import _
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager, get_records_pager
from odoo.addons.payment.controllers.portal import WebsitePayment


class MyaccountAddons(http.Controller):
    @http.route('/my/home', type='http', auth='public', website=True)
    def sale_details(self, **kwargs):
        sale_details = http.request.env['sale.order'].search([])

        return http.request.render('myaccount_addons.portal_my_auctions', {
            'my_details': sale_details})

    @http.route('/my/home', type='http', auth='public', website=True)
    def execute_query(self):
        user = http.request.env['res.users'].browse(request.uid).partner_id.id
        query = "Select (select sum(residual_signed) from account_invoice where partner_id=%s) as a,(select sum(amount_total_signed) from account_invoice where partner_id=%s ) as b,(select amount from account_payment where partner_id=%s and id=(SELECT MAX(id) FROM account_payment where partner_id=%s and state='posted') ) as c,(select create_date from account_payment where partner_id=%s and create_date=(SELECT MAX(create_date) FROM account_payment where partner_id=%s and state='posted') ) as d,(select currency_id from account_invoice where partner_id=%s and create_date=(SELECT MAX(create_date) FROM account_payment where partner_id=%s and state='posted')) as e"
        #query = "Select (select sum(residual_signed) from account_invoice where partner_id=%s) as a, (select sum(amount_total_signed) from account_invoice where partner_id='%s' ) as b,(select amount from account_payment where partner_id='%s' and payment_date=(SELECT MAX(payment_date) FROM account_payment where partner_id='%s' and state='posted') ) as c,(select payment_date from account_payment where partner_id='%s' and payment_date=(SELECT MAX(payment_date) FROM account_payment where partner_id='%s' and state='posted') ) as d"
        vars = (user, user, user, user, user, user,user,user)
        request.cr.execute(query,vars)
        companies1 = request.cr.dictfetchall()
        return http.request.render('myaccount_addons.portal_my_auctions', {
            # pass company details to the webpage in a variable
            'companies1': companies1})


    @http.route(['/balance/Overdue'], type='http', auth="public", website=True)
    def wallet_balance_confirm(self, **post):
        product = request.env['product.product'].sudo().search([('name', '=', 'Wallet Recharge')])
        name = "Bulk Payment"
        product_id = product.id
        add_qty = 0
        set_qty = 0
        product.update({'lst_price': post['amount']})
        # product.lst_price = post['amount']
        request.website.sale_get_order(force_create=1)._cart_update(
            product_id=int(product_id),
            add_qty=float(add_qty),
            set_qty=float(set_qty),
            name = Char(name),
        )
        return request.redirect("/shop/payment/transaction")

    @http.route(['/wallet/balance/Overdue'], type='http', auth="public", website=True)
    def wallet_balance_confirm(self, **post):
        product = request.env['product.product'].sudo().search([('name', '=', 'Wallet Recharge')])

        product_id = product.id
        add_qty = 0
        set_qty = 0
        product.update({'lst_price': post['Overdue']})
        # product.lst_price = post['amount']
        request.website.sale_get_order(force_create=1)._cart_update(
            product_id=int(product_id),
            add_qty=float(add_qty),
            set_qty=float(set_qty),
        )
        return request.redirect("/shop/cart")

    @http.route('/shop/payment/validate', type='http', auth="public", website=True)
    def payment_validate(self, transaction_id=None, sale_order_id=None, **post):
        """ Method that should be called by the server when receiving an update
        for a transaction. State at this point :

         - UDPATE ME
        """

        if sale_order_id is None:
            order = request.website.sale_get_order()
        else:
            order = request.env['sale.order'].sudo().browse(sale_order_id)
            assert order.id == request.session.get('sale_last_order_id')

        if transaction_id:
            tx = request.env['payment.transaction'].sudo().browse(transaction_id)
            assert tx in order.transaction_ids()
        elif order:
            tx = order.get_portal_last_transaction()
        else:
            tx = None

        if not order or (order.amount_total and not tx):
            return request.redirect('/shop')

        # if payment.acquirer is credit payment provider
        for line in order.order_line:
            if len(order.order_line) == 1:
                if line.product_id.name == 'Wallet Recharge':
                    wallet_transaction_obj = request.env['website.wallet.transaction']
                    wallet_create = wallet_transaction_obj.sudo().create({
                        'wallet_type': 'credit',
                        'partner_id': order.partner_id.id,
                        'sale_order_id': order.id,
                        'reference': 'sale_order',
                        'amount': order.order_line.product_id.lst_price * order.order_line.product_uom_qty,
                        'currency_id': order.pricelist_id.currency_id.id,
                        'status': 'done'
                    })
                    wallet_create.wallet_transaction_email_send()  # Mail Send to Customer
                    order.partner_id.update({
                        'wallet_balance': order.partner_id.wallet_balance + order.order_line.product_id.lst_price * order.order_line.product_uom_qty})
                    order.with_context(send_email=True).action_confirm()
                    request.website.sale_reset()

        if (not order.amount_total and not tx) or tx.state in ['pending', 'done', 'authorized']:
            if (not order.amount_total and not tx):
                # Orders are confirmed by payment transactions, but there is none for free orders,
                # (e.g. free events), so confirm immediately
                order.with_context(send_email=True).action_confirm()
        elif tx and tx.state == 'cancel':
            # cancel the quotation
            order.action_cancel()

        # clean context and session, then redirect to the confirmation page
        request.website.sale_reset()
        if tx and tx.state == 'draft':
            return request.redirect('/shop')

        PaymentProcessing.remove_payment_transaction(tx)
        return request.redirect('/shop/confirmation')




