#! /usr/bin/python

import email, smtplib, os, datetime, csv, subprocess, locale, time, inspect, sys
from lxml import etree
from email.mime.text import MIMEText

# allow import from subdirectory
currentDir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
btcuDir = currentDir + '/bitcoinutilities'
if btcuDir not in sys.path:
    sys.path.append(btcuDir)


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
            print(ex)
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


# test code
if __name__ == "__main__":
    if not os.path.exists('tmp'):
        os.mkdir('tmp')
    locale.setlocale(locale.LC_TIME, '')

    # information gathering
    #mailer = Mailer()
    #infos = mailer.Parse("../Ihre_Anfrage.mbox")

    infos = {}
    infos['Vor- und Nachname'] = "xx"
    infos['Strasse und Hausnummer'] = "xx"
    infos['Postleitzahl'] = "xx"
    infos['Ort'] = "xx"
    infos['Ihre E-Mail'] = "xx@xx.ch"
    infos['Rufnummer (fur Ruckfragen)'] = "xx"
    infos['Name des Beschenkten'] = "xx"
    #infos['VoucherNumber']
    infos['FlightType'] = "Genussflug"
    infos['FlightPrice'] = "200"
    #infos['QrInfoFile'])
    infos['xbtAddress'] = "xx"

    overview = Overview('../GutscheineUebersicht.csv')
    voucherNumber = overview.findNextVoucherNbr()
    infos['VoucherNumber'] = str(voucherNumber)

    # find a bitcoin address
    #bitCoinAddr = BitCoinAddr('../BitCoinXPub.txt').GetNext()
    #infos['xbtAddress'] = str(bitCoinAddr)
    #print('*' + infos['xbtAddress'] + '*')

    # generate the qr codes
    qrInfoString = 'http://paraeasy.ch\n' \
                 + 'GutscheinNr: ' + infos['VoucherNumber']        + '\n' \
                 + 'FlugTyp: '     + infos['FlightType']           + '\n' \
                 + 'Passagier: '   + infos['Name des Beschenkten'] + '\n' \
                 + 'BitCoin: '     + infos['xbtAddress'] + '\n'
    print(qrInfoString)
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
    p.stdin.write(qrInfoString.encode())
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

    print(infos)

