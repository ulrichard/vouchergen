#! /usr/bin/python

import email, smtplib, tidy, os, datetime, csv, subprocess, locale, time, inspect, sys
from lxml import etree
from email.mime.text import MIMEText

# allow import from subdirectory
currentDir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
btcuDir = currentDir + '/bitcoinutilities'
if btcuDir not in sys.path:
    sys.path.append(btcuDir)

import pycoin.key.BIP32Node
import blockchain_info


# see http://docs.python.org/2/library/email-examples.html
class Mailer:
    def Parse(self, mailFile):
        fp = open(mailFile, 'rb')
        msg = email.message_from_file(fp)
        cont = msg.get_payload()
        options = dict(output_xhtml=1, add_xml_decl=0, indent=1, tidy_mark=0)
        td = tidy.parseString(cont, **options)
        ss = str(td)
        ss = ss[ss.find('<table '):]
        ss = ss[:ss.find('</table>') + 8]
        ss = ss[:ss.find('colspan')]
        ss = ss[:ss.rfind('<tr>')]
        ss = ss.replace('<tbody>', '');
        ss = ss.replace('&uuml;', 'u');
        ss = ss.replace('&auml;', 'a');
        ss = ss.replace('&ouml;', 'o');
        ss = ss.replace('&Auml;', 'A');
        ss = ss.replace('&Ouml;', 'O');
        ss = ss.replace('&uuml;', 'u');
        ss = ss + '</table>'
        #http://stackoverflow.com/questions/6325216/parse-html-table-to-python-list
        table = etree.XML(ss)
    
        infos = {}

        # direct infos
        rows = iter(table)
        for row in rows:
            values = [col.text for col in row]
            key = str(values[0]).replace('\n', '').strip()
            val = str(values[2]).replace('\n', '').strip()
            infos[key] = val

        # processed infos
        flightTypeAndPrice = infos['Bitte wahlen Sie Ihren Flug aus']
        flights = {
                    'Schnupperflug fur 160.00 CHF'       : ['Schnupperflug', '160'],
                    'Genussflug fur 200.00 CHF'          : ['Genussflug',    '200'],
                    'Panoramaflug fur 250.00 CHF'        : ['Panoramaflug',  '250'],
                    'Pilot fur einen Tag fur 520.00 CHF' : ['Pilot 4 a day', '520'],
                  }
        infos['FlightType']  = flights[flightTypeAndPrice][0]
        infos['FlightPrice'] = flights[flightTypeAndPrice][1]

        #meta infos
        infos['Subject'] = msg['Subject']
        
        return infos

    def Send(self):
      msg = MIMEText("Hallo")  

class LaTex:
    def __init__(self, values, directory):
        self.values = values
        self.directory = directory

    def Prepare(self, fileName):
        fpi = open(fileName, 'rt')
        ss = fpi.read()
        
        numFlights = 1

        ss = ss.replace('@CustomerName@',    self.values['Vor- und Nachname'])
        ss = ss.replace('@CustomerAddress@', self.values['Strasse und Hausnummer'])
        ss = ss.replace('@CustomerZIP@',     self.values['Postleitzahl'])
        ss = ss.replace('@CustomerCity@',    self.values['Ort'])
        ss = ss.replace('@CustomerEMail@',   self.values['Ihre E-Mail'])
        ss = ss.replace('@CustomerPhone@',   self.values['Rufnummer (fur Ruckfragen)'])
        ss = ss.replace('@PassengerName@',   self.values['Name des Beschenkten'])
        ss = ss.replace('@VoucherNumber@',   self.values['VoucherNumber'])
        ss = ss.replace('@ValidUntil@',      (datetime.date.today() + datetime.timedelta(days=400)).strftime('%B %Y'))
        ss = ss.replace('@FlightType@',      self.values['FlightType'])
        ss = ss.replace('@FlightCount@',     str(numFlights))
        ss = ss.replace('@FlightPrice@',     self.values['FlightPrice'])
        ss = ss.replace('@TotalPrice@',      str(numFlights * int(self.values['FlightPrice'])))
        ss = ss.replace('@QrInfoFile@',      self.values['QrInfoFile'])    
        ss = ss.replace('@xbtAddress@',      self.values['xbtAddress'])    

        if not os.path.exists(self.directory):
            os.makedirs(self.directory)
        outFileName = self.directory + '/' + fileName
        fpo = open(outFileName, 'wt')
        fpo.write(ss)

        return outFileName

    def ToPdf(self, fileName):
        subprocess.call(['pdflatex', fileName]) 
        fileName = os.path.basename(fileName.replace('.tex', ''))
        if fileName == 'Rechnung':
            persName = self.values['Vor- und Nachname']
        else:
            persName = self.values['Name des Beschenkten']
        pdfName = os.getcwd() + '/../pdf/' + self.values['VoucherNumber'] + '_' + fileName + '_' + persName + '.pdf'
        os.rename(os.getcwd() + '/' + fileName + '.pdf', pdfName)
        return pdfName

class Overview:
    def __init__(self, fileName):
        self.fileName = fileName

    def findNextVoucherNbr(self):
        today = datetime.date.today()
        pref = '%02d%02d%02d' % (today.year % 1000, today.month, today.day)
        cnt = 0
        try:
            for row in csv.reader(open(self.fileName, 'rt'), delimiter=';'):
                if len(row) >= 6:
                    vfld = row[0]
                    if vfld[0:6] == pref:
                        cnt = int(vfld[6:])
            return pref + ('%02d' % (cnt + 1))              
        except Exception as ex:
            print ex
            return pref + '01'
        

    def addEntry(self, values):
        csvwriter = csv.writer(open(self.fileName, 'at'), delimiter=';')
        row = [   values['VoucherNumber']
                , values['FlightType']
                , values['Name des Beschenkten']
                , values['Vor- und Nachname'] + ', ' + values['Strasse und Hausnummer'] 
                    + ', ' + values['Postleitzahl'] + ' ' + values['Ort']
                , values['FlightPrice']
                , infos['xbtAddress']
              ]
        csvwriter.writerow(row)

class BitCoinAddr:
    def __init__(self, fileName):
        fp = open(fileName, 'rt')
        self.xpub = fp.readline().rstrip('\n')
        fp.close()

    def GetNext(self):
        kk = pycoin.key.BIP32Node.BIP32Node.from_hwif(self.xpub)
        for i in range(99999):
            keypath = "0/%d.pub" % i
            addr = kk.subkey_for_path(keypath).address()
            #print i, j, addr
            ledger = blockchain_info.blockchain(addr, False)
            if ledger.tx_count() == 0:
                return addr


# test code
if __name__ == "__main__":
    if not os.path.exists('tmp'):
        os.mkdir('tmp')
    locale.setlocale(locale.LC_TIME, '')

    # information gathering
    mailer = Mailer()
    infos = mailer.Parse("../Ihre_Anfrage.mbox")
    overview = Overview('../GutscheineUebersicht.csv')
    voucherNumber = overview.findNextVoucherNbr()
    infos['VoucherNumber'] = str(voucherNumber)

    # find a bitcoin address
    bitCoinAddr = BitCoinAddr('../BitCoinXPub.txt').GetNext()
    infos['xbtAddress'] = str(bitCoinAddr)
    print('*' + infos['xbtAddress'] + '*')

    # generate the qr codes
    qrInfoString = 'http://paraeasy.ch\n' \
                 + 'GutscheinNr: ' + infos['VoucherNumber']        + '\n' \
                 + 'FlugTyp: '     + infos['FlightType']           + '\n' \
                 + 'Passagier: '   + infos['Name des Beschenkten'] + '\n' \
                 + 'BitCoin: '     + infos['xbtAddress'] + '\n'
    print qrInfoString
    infof = open('../pdf/' + voucherNumber + '_infos.txt', 'wt')
    infof.write(qrInfoString)
    infof.close()

    key_id = os.environ['GPGKEY']
    subprocess.call(['gpg', '-u', key_id, '--clearsign', 'pdf/' + voucherNumber + '_infos.txt'], cwd='../')
    infofs = open('../pdf/' + voucherNumber + '_infos.txt.asc', 'rt')
    qrInfoString = infofs.read()
    infofs.close()

    os.remove('../pdf/' + voucherNumber + '_infos.txt')
    os.remove('../pdf/' + voucherNumber + '_infos.txt.asc')

    infos['QrInfoFile'] = 'tmp/qr_' + infos['VoucherNumber'] + '.png'
    print('writing ', infos['QrInfoFile'])

    p = subprocess.Popen(['qrencode', '-o', infos['QrInfoFile']], stdout=subprocess.PIPE, stdin=subprocess.PIPE)
    p.stdin.write(qrInfoString)
    p.communicate()[0]
    p.stdin.close()

    if not os.path.isfile(infos['QrInfoFile']):
        raise ValueError('qr image file not written')

    # prepare the documents    
    latex = LaTex(infos, 'tmp')
    files = ['Gutschein.tex', 'Rechnung.tex']
    for texFile in files:
        pdfFile = latex.ToPdf(latex.Prepare(texFile))
        subprocess.call(['evince', pdfFile])
        subprocess.call(['git', 'add', str(pdfFile)], cwd='../')

    # accounting
    overview.addEntry(infos)
    subprocess.call(['git', 'add', 'GutscheineUebersicht.csv'], cwd='../')

    print infos

