import json
import re
from kivy.clock import Clock
from kivymd.uix.banner import MDBanner
from kivymd.uix.textfield import MDTextFieldRound
from plyer import gps
from kivy.clock import mainthread
from kivy.utils import platform
from kivy.metrics import dp
from kivy.uix.screenmanager import Screen
from kivymd.app import MDApp
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import ObjectProperty
from kivymd.uix.button import MDFillRoundFlatButton
from kivymd.uix.datatables import MDDataTable
from kivymd.uix.label import MDLabel
from kivymd.uix.menu import MDDropdownMenu
from plyer import call
from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse, Line
import requests
from PIL import Image
from pyzbar.wrapper import ZBarSymbol


class DeliveryControlApp(MDApp):
    def build(self):
        return


class CompanyScreen(Screen):
    menu = MDDropdownMenu

    error_banner = ObjectProperty(MDBanner)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(self.event_binding)

    def event_binding(self, dt):
        companies_selection = []
        try:
            response = requests.get('https://developer.mercaditu.com/api/authenticated/my/organizations',
                                    headers={'Authorization': 'Bearer 5|bWbmJ2bfFsDLOIcQ5rHKZCvmzrYY2uez0SpP82Sr',
                                             'Accept': 'application/json',
                                             'Content-type': 'application/json'})
            companies = response.json()
            if len(companies) != 0:
                for company in companies:
                    companies_selection.append({"icon": "account-box", "text": company["following"]["handle"]})

                self.menu = MDDropdownMenu(
                    caller=self.ids.company_text,
                    items=companies_selection,
                    position="bottom",
                    width_mult=4,
                    callback=self.set_item
                )
                self.menu.bind(on_release=self.set_item)
                self.menu.set_menu_properties(0)
            else:
                raise Exception('La Empresa no se encuentra')
        except Exception as e:
            self.error_banner.text = [str(e)]
            self.error_banner.right_action = ["CLOSE", lambda x: self.error_banner.hide()]
            self.error_banner.show()

    def set_item(self, *args):
        self.ids.company_text.text = args[0].text
        self.menu.dismiss()

    def go_to_scan_page(self):
        self.manager.transition.direction = 'left'
        self.manager.current = 'scanner_screen'


class LoginScreen(Screen):
    email = ObjectProperty(None)
    password = ObjectProperty(MDTextFieldRound)
    layout = ObjectProperty(BoxLayout)
    api_file = ObjectProperty(None)
    stored_api_key = ObjectProperty(None)
    error_banner = ObjectProperty(MDBanner)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(self.check_stored_api_key)

    def check_stored_api_key(self, dt):
        self.api_file = open('api_key.json')
        self.stored_api_key = json.load(self.api_file)
        self.api_file.close()

        if self.stored_api_key["remember_me"] == 'true':
            self.do_login()

    def do_login(self):
        try:
            response = None
            if self.stored_api_key["mercaditu"].strip() != '':
                response = requests.get('https://developer.mercaditu.com/api/user',
                                        headers={'Authorization': 'Bearer ' + self.stored_api_key["mercaditu"],
                                                 'Accept': 'application/json',
                                                 'Content-type': 'application/json'})
            elif self.password.text != '':
                response = requests.get('https://developer.mercaditu.com/api/user',
                                        headers={'Authorization': 'Bearer ' + self.password.text,
                                                 'Accept': 'application/json',
                                                 'Content-type': 'application/json'})
            else:
                raise Exception("La contraseña no es valida. Favor intentar nuevamente")
            if response is not None:
                if response.status_code == 200:
                    self.manager.transition.direction = 'left'
                    self.manager.current = 'company_screen'
                else:
                    raise Exception("La contraseña no es valida. Favor intentar nuevamente")
            else:
                raise Exception("La contraseña no es valida. Favor intentar nuevamente")
        except Exception as e:
            self.error_banner.text = [str(e)]
            self.error_banner.right_action = ["CLOSE", lambda x: self.error_banner.hide()]
            self.error_banner.show()

    def remember_me(self, checkbox, is_active):
        if is_active:
            self.stored_api_key["mercaditu"] = self.password.text
            self.stored_api_key["remember_me"] = "true"
        else:
            self.stored_api_key["mercaditu"] = ''
            self.stored_api_key["remember_me"] = "false"
        with open('api_key.json', 'w', encoding='utf-8') as outfile:
            json.dump(self.stored_api_key, outfile, ensure_ascii=False, indent=4)


class CameraScreen(Screen):
    def capture(self):
        camera = self.ids['camera']
        camera.export_to_png("Signature.png")
        image = Image.open('Signature.png')
        image = image.resize((320, 240))
        image.save('Signature.png')
        self.manager.transition.direction = 'right'
        self.manager.current = 'success_screen'


class DeliveryControlLayout(BoxLayout):
    pass


class BarcodeScanner(Screen):
    screen_manager = ObjectProperty(Screen)
    barcode = ObjectProperty(None)
    zbarcam = ObjectProperty(None)
    barcode_layout = ObjectProperty(BoxLayout)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(self.event_binding)

    def event_binding(self, dt):
        self.barcode.bind(text=self.text_change_callback)

    def text_change_callback(self, obj, value):
        value = value[2:]
        value = value[:-1]
        if re.match("(\d{3})-(\d{3})-(\d{7})", value):
            self.manager.get_screen('invoice_info').barcode.text = value
            self.manager.transition.direction = 'left'
            self.manager.current = 'invoice_info'


class InvoiceInfo(Screen):
    screen_manager = ObjectProperty(Screen)
    barcode = ObjectProperty(MDLabel)
    fecha_factura = ObjectProperty(MDLabel)
    cliente = ObjectProperty(MDLabel)
    invoice = ObjectProperty(BoxLayout)
    invoice_table = ObjectProperty(BoxLayout)

    # profiles = {}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        try:
            gps.configure(on_location=self.on_location,
                          on_status=self.on_status)
        except NotImplementedError:
            import traceback
            traceback.print_exc()
            self.gps_status = 'GPS is not implemented for your platform'
        if platform == "android":
            print("gps.py: Android detected. Requesting permissions")
            self.request_android_permissions()

    def start(self, minTime, minDistance):
        gps.start(minTime, minDistance)

    def stop(self):
        gps.stop()

    @mainthread
    def on_location(self, **kwargs):
        self.gps_location = '\n'.join([
            '{}={}'.format(k, v) for k, v in kwargs.items()])
        print(self.gps_location)

    @mainthread
    def on_status(self, stype, status):
        self.gps_status = 'type={}\n{}'.format(stype, status)

    def on_pause(self):
        gps.stop()
        return True

    def on_resume(self):
        gps.start(1000, 0)
        pass

    def on_enter(self, *args):
        invoice_data = []
        self.fecha_factura.text = ""
        self.cliente.text = ""
        self.invoice_table.clear_widgets()
        try:
            if self.manager.get_screen('company_screen').company_text is not None:
                company = self.manager.get_screen('company_screen').company_text.text
            else:
                raise Exception('Disculpe la empresa no se encuentra')

            self.barcode.text = self.barcode.text
            if (len(self.barcode.text) == 0):
                raise Exception('Disculpe el numero de factura no se encuentra')
            invoice_query = 'https://developer.mercaditu.com/api/protected/profiles/' + company + '/backoffice/invoice/' + self.barcode.text + '?include=details,buyer'
            response_invoice = requests.get(invoice_query,
                                            headers={
                                                'Authorization': 'Bearer 5|bWbmJ2bfFsDLOIcQ5rHKZCvmzrYY2uez0SpP82Sr',
                                                'Accept': 'application/json',
                                                'Content-type': 'application/json'})
            if response_invoice.status_code == 200:
                invoice_info = response_invoice.json()
            else:
                raise Exception('Disculpe error en conexion')
            if len(invoice_info) != 0:
                self.fecha_factura.text = invoice_info['date']
                self.cliente.text = invoice_info['buyer']['handle']
                for inv in invoice_info['details']:
                    invoice_data.append(('1', inv['item_name'],
                                         inv['quantity'],
                                         inv['price']))
                invoice_data.append(('', '', '', ''))
                invoice_table = MDDataTable(
                    column_data=[
                        ("No.", dp(30)),
                        ("Nombre de Item", dp(30)),
                        ("Cantidad", dp(60)),
                        ("Precio", dp(30))
                    ],
                    row_data=invoice_data
                )
                self.invoice_table.add_widget(invoice_table)
            else:
                raise Exception('La factura no se encuentra')
        except Exception as e:
            self.error_banner.text = [str(e)]
            self.error_banner.right_action = ["CLOSE", lambda x: self.error_banner.hide()]
            self.error_banner.show()

    def request_android_permissions(self):
        from android.permissions import request_permissions, Permission

        def callback(permissions, results):
            """
            Defines the callback to be fired when runtime permission
            has been granted or denied. This is not strictly required,
            but added for the sake of completeness.
            """
            if all([res for res in results]):
                print("callback. All permissions granted.")
            else:
                print("callback. Some permissions refused.")

        request_permissions([Permission.ACCESS_COARSE_LOCATION,
                             Permission.ACCESS_FINE_LOCATION], callback)

    def get_location_send_mail(self):
        company_name = self.manager.get_screen('company_screen').ids.company_text.text
        url = "https://developer.mercaditu.com/api/protected/profiles/{}/backoffice/email/200".format(company_name)
        params = {"number": self.barcode.text, "lat": 51.2343564, "lng": 4.4286108}
        response = requests.post(url, data=params,
                                 headers={'Authorization': 'Bearer 5|bWbmJ2bfFsDLOIcQ5rHKZCvmzrYY2uez0SpP82Sr',
                                          'Accept': 'application/json',
                                          'Content-type': 'application/json'})
        status = response.json()
        print(status)
        self.manager.current = 'success_screen'


class DialCallButton(MDFillRoundFlatButton):

    def dial(self, *args):
        call.makecall('0981831510')


class SignatureScreen(Screen):

    def save_signature(self):
        print(self.ids.signature.size)
        self.ids.signature.export_to_png("a.png")
        self.manager.current = 'success_screen'


class Signature(Widget):

    def on_touch_down(self, touch):
        with self.canvas:
            Color(1, 1, 0)
            d = 50.
            Ellipse(pos=(touch.x - d / 2, touch.y - d / 2), size=(d, d))
            touch.ud['line'] = Line(points=(touch.x, touch.y))

    def on_touch_move(self, touch):
        touch.ud['line'].points += [touch.x, touch.y]


class FinalScreen(Screen):
    pass


DeliveryControlApp().run()
