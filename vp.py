import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from lxml import etree
import json
import os
import time
import streamlit as st
import threading
import os
from dotenv import load_dotenv

# Carregar as variáveis de ambiente do arquivo .env
load_dotenv(dotenv_path='vp.env')  # Especifica o caminho correto do seu arquivo .env se necessário


# Carregar as variáveis sensíveis
vale_pedagio_url = os.getenv('VALE_PEDAGIO_URL')
# Carregar os valores das variáveis de ambiente
codigodeacesso_env = os.getenv('VALE_PEDAGIO_CODIGO_ACESSO')
login_env = os.getenv('VALE_PEDAGIO_LOGIN')
senha_env = os.getenv('VALE_PEDAGIO_SENHA')
vale_pedagio_url_impressao = os.getenv('VALE_PEDAGIO_URL_IMPRESSAO')
vale_pedagio_url_sgf = os.getenv('VALE_PEDAGIO_URL_SGF')
soap_action_autenticar = os.getenv('SOAP_ACTION_AUTENTICAR')
soap_action_comprar = os.getenv('SOAP_ACTION_COMPRAR')
user_agent = os.getenv('USER_AGENT')
referer = os.getenv('REFERER')


# Variável para controlar o loop
loop_compras_ativo = False

# Caminho do arquivo JSON para armazenar compras realizadas
ARQUIVO_COMPRAS = 'compras_realizadas.json'

# Função para converter cookies string para dicionário
def parse_cookies(cookies_str):
    cookies = {}
    for cookie in cookies_str.split(';'):
        name, value = cookie.strip().split('=', 1)
        cookies[name] = value
    return cookies

# Função para carregar compras realizadas do arquivo JSON
def carregar_compras_realizadas():
    if os.path.exists(ARQUIVO_COMPRAS):
        with open(ARQUIVO_COMPRAS, 'r') as f:
            return json.load(f)
    return {}

# Função para salvar compras realizadas no arquivo JSON
def salvar_compras_realizadas(compras):
    with open(ARQUIVO_COMPRAS, 'w') as f:
        json.dump(compras, f, indent=4)

# Função para verificar se a viagem já foi comprada com base no número do documento
def viagem_ja_comprada(documento):
    compras_realizadas = carregar_compras_realizadas()
    return documento in compras_realizadas

# Função para registrar a compra realizada
def registrar_compra_realizada(documento):
    compras_realizadas = carregar_compras_realizadas()
    compras_realizadas[documento] = True
    salvar_compras_realizadas(compras_realizadas)

# Função para remover namespaces do XML
def remove_namespaces(tree):
    for elem in tree.getiterator():
        elem.tag = elem.tag.split('}')[-1]
    etree.cleanup_namespaces(tree)
    return tree

# Função para autenticar o usuário no sistema de Vale-Pedágio
def autenticar_usuario():
    url = vale_pedagio_url
    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': soap_action_autenticar
    }
    envelope = etree.Element('{http://schemas.xmlsoap.org/soap/envelope/}Envelope',
                            nsmap={
                                'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
                                'xsd': 'http://www.w3.org/2001/XMLSchema',
                                'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
                                'cgmp': 'http://cgmp.com'
                            })
    body = etree.SubElement(envelope, '{http://schemas.xmlsoap.org/soap/envelope/}Body')
    autenticar_usuario = etree.SubElement(body, '{http://cgmp.com}autenticarUsuario',
                                        attrib={'{http://schemas.xmlsoap.org/soap/envelope/}encodingStyle': 'http://schemas.xmlsoap.org/soap/encoding/'})
    
    codigodeacesso = etree.SubElement(autenticar_usuario, 'codigodeacesso', attrib={etree.QName('xsi', 'type'): 'xsd:string'})
    codigodeacesso.text = codigodeacesso_env
    
    login = etree.SubElement(autenticar_usuario, 'login', attrib={etree.QName('xsi', 'type'): 'xsd:string'})
    login.text = login_env
    
    senha = etree.SubElement(autenticar_usuario, 'senha', attrib={etree.QName('xsi', 'type'): 'xsd:string'})
    senha.text = senha_env
    
    soap_request = etree.tostring(envelope, pretty_print=True, xml_declaration=True, encoding='UTF-8')
    
    try:
        response = requests.post(url, data=soap_request, headers=headers, timeout=30)
        response.raise_for_status()

        response_content = etree.fromstring(response.content)
        response_content = remove_namespaces(response_content)

        autenticar_usuario_return = response_content.find('.//autenticarUsuarioReturn')
        if autenticar_usuario_return is not None:
            sessao_element = autenticar_usuario_return.find('.//sessao')
            if sessao_element is not None:
                return sessao_element.text
        return None
    except requests.exceptions.RequestException as e:
        st.write(f"Erro na requisição SOAP: {e}")
        return None

# Função para comprar viagem
def comprar_viagem(sessao, rota, placa, n_eixos, inicio_vigencia, fim_vigencia):
    url = vale_pedagio_url

    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': soap_action_comprar
    }

    envelope = etree.Element('{http://schemas.xmlsoap.org/soap/envelope/}Envelope',
                            nsmap={
                                'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
                                'xsd': 'http://www.w3.org/2001/XMLSchema',
                                'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
                                'cgmp': 'http://cgmp.com'
                            })

    body = etree.SubElement(envelope, '{http://schemas.xmlsoap.org/soap/envelope/}Body')
    comprar_viagem = etree.SubElement(body, '{http://cgmp.com}comprarViagem',
                                    attrib={'{http://schemas.xmlsoap.org/soap/envelope/}encodingStyle': 'http://schemas.xmlsoap.org/soap/encoding/'})

    etree.SubElement(comprar_viagem, 'sessao', attrib={etree.QName('xsi', 'type'): 'xsd:long'}).text = sessao
    etree.SubElement(comprar_viagem, 'rota', attrib={etree.QName('xsi', 'type'): 'xsd:string'}).text = rota
    etree.SubElement(comprar_viagem, 'placa', attrib={etree.QName('xsi', 'type'): 'xsd:string'}).text = placa
    etree.SubElement(comprar_viagem, 'nEixos', attrib={etree.QName('xsi', 'type'): 'xsd:int'}).text = str(n_eixos)
    etree.SubElement(comprar_viagem, 'inicioVigencia', attrib={etree.QName('xsi', 'type'): 'xsd:date'}).text = inicio_vigencia
    etree.SubElement(comprar_viagem, 'fimVigencia', attrib={etree.QName('xsi', 'type'): 'xsd:date'}).text = fim_vigencia

    soap_request = etree.tostring(envelope, pretty_print=True, xml_declaration=True, encoding='UTF-8')

    try:
        response = requests.post(url, data=soap_request, headers=headers, timeout=30)
        response.raise_for_status()

        root = etree.fromstring(response.content)
        root = remove_namespaces(root)

        numero = None
        status = None
        for element in root.iter():
            if element.tag.endswith('numero'):
                numero = element.text
            if element.tag.endswith('status'):
                status = element.text

        if status == '0':
            st.write(f"Compra realizada com sucesso para rota {rota}. Número da viagem: {numero}")
            return numero
        else:
            st.write(f"Erro na compra da viagem para rota {rota}: Código de status {status}")
            return None
    except requests.exceptions.RequestException as e:
        st.write(f"Erro na requisição SOAP para rota {rota}: {e}")
        return None

# Função para imprimir recibo
def imprimir_recibo(sessao, numero_viagem, imprimir_observacoes):
    url_impressao = vale_pedagio_url_impressao
    payload = {
        'sessao': sessao,
        'viagem': numero_viagem,
        'imprimirObservacoes': str(imprimir_observacoes).lower()
    }

    try:
        response = requests.post(url_impressao, data=payload, timeout=30)
        response.raise_for_status()
        st.write(f"Recibo da viagem {numero_viagem} foi impresso com sucesso.")
    except requests.exceptions.RequestException as e:
        st.write(f"Erro ao imprimir o recibo para a viagem {numero_viagem}: {e}")

# Função para processar a viagem
def processar_viagem(placa, fazenda, conjunto):
    sessao = autenticar_usuario()
    if not sessao:
        st.write("Erro ao autenticar o usuário. Verifique as credenciais e tente novamente.")
        return

    inicio_vigencia = datetime.today().strftime('%Y-%m-%d')
    fim_vigencia = (datetime.today() + timedelta(days=5)).strftime('%Y-%m-%d')

    conjunto = conjunto.lower()
    if conjunto == 'bitrem':
        n_eixos_ida = 4
        n_eixos_volta = 7
    elif conjunto == 'tritrem':
        n_eixos_ida = 6
        n_eixos_volta = 9
    else:
        st.write("Tipo de conjunto não reconhecido.")
        return

    rota_ida = f'FAZ {fazenda} - IDA'
    rota_volta = f'FAZ {fazenda} - VOLTA'

    numero_viagem_ida = comprar_viagem(sessao, rota_ida, placa, n_eixos_ida, inicio_vigencia, fim_vigencia)
    if numero_viagem_ida:
        imprimir_recibo(sessao, numero_viagem_ida, True)
    else:
        st.write(f"Falha na compra da viagem de ida para {rota_ida}")

    numero_viagem_volta = comprar_viagem(sessao, rota_volta, placa, n_eixos_volta, inicio_vigencia, fim_vigencia)
    if numero_viagem_volta:
        imprimir_recibo(sessao, numero_viagem_volta, True)
    else:
        st.write(f"Falha na compra da viagem de volta para {rota_volta}")

# Função para converter cookies string para dicionário
def parse_cookies(cookies_str):
    cookies = {}
    for cookie in cookies_str.split(';'):
        name, value = cookie.strip().split('=', 1)
        cookies[name] = value
    return cookies

# Função para carregar compras realizadas do arquivo JSON
def carregar_compras_realizadas():
    if os.path.exists(ARQUIVO_COMPRAS):
        with open(ARQUIVO_COMPRAS, 'r') as f:
            return json.load(f)
    return {}

# Função para salvar compras realizadas no arquivo JSON
def salvar_compras_realizadas(compras):
    with open(ARQUIVO_COMPRAS, 'w') as f:
        json.dump(compras, f, indent=4)

# Função para verificar se a viagem já foi comprada com base no número do documento
def viagem_ja_comprada(documento):
    compras_realizadas = carregar_compras_realizadas()
    return documento in compras_realizadas

# Função para registrar a compra realizada
def registrar_compra_realizada(documento):
    compras_realizadas = carregar_compras_realizadas()
    compras_realizadas[documento] = True  # Marca o documento como já processado
    salvar_compras_realizadas(compras_realizadas)

# Função para capturar as informações usando os cookies fornecidos
def capturar_informacoes(cookies):
    url = vale_pedagio_url_sgf
    
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7,es;q=0.6",
        "Connection": "keep-alive",
        "Referer": referer,
        "User-Agent": user_agent
    }

    # Fazendo a requisição GET com os cookies
    response = requests.get(url, headers=headers, cookies=cookies)

    # Verificando se a requisição foi bem-sucedida
    if response.status_code == 200:
        st.write("Requisição bem-sucedida!")
        soup = BeautifulSoup(response.text, 'html.parser')

        # Loop para capturar informações de várias linhas (ctl03 a ctl12)
        for i in range(3, 10):  # ctl03 até ctl12
            try:
                fornecedor = soup.find('span', id=f"ctl48_ctl01_ctl{i:02}_CdFornecedorEquipamentoDESC")
                projeto = soup.find('span', id=f"ctl48_ctl01_ctl{i:02}_CdProjetoDESC")
                documento = soup.find('span', id=f"ctl48_ctl01_ctl{i:02}_CdDocumentoDESC")
                equipamento = soup.find('span', id=f"ctl48_ctl01_ctl{i:02}_CdEquipamentoDESC")
                tipo_conjunto = soup.find('span', id=f"ctl48_ctl01_ctl{i:02}_CdTipoConjuntoDESC")
                situacao = soup.find('span', id=f"ctl48_ctl01_ctl{i:02}_TipSituacaoDESC")

                # Verificar se todos os elementos foram encontrados
                if not all([fornecedor, projeto, documento, equipamento, tipo_conjunto, situacao]):
                    st.write(f"Linha {i-2}: Informações incompletas, alguns elementos não foram encontrados.")
                    st.write("-" * 50)
                    continue

                fornecedor = fornecedor.text
                projeto = projeto.text
                documento = documento.text
                equipamento = equipamento.text
                tipo_conjunto = tipo_conjunto.text.strip().lower()
                situacao = situacao.text

                # Lógica para evitar projetos ignorados
                if projeto in ["SÃO MANOEL GLEBA A - CPG", "SANTO ANTÔNIO", "NOSSA SENHORA APARECIDA XV"]:
                    st.write(f"Linha {i-2}: Projeto '{projeto}' ignorado.")
                    continue

                # Verificação de compra repetida
                if viagem_ja_comprada(documento):
                    st.write(f"Linha {i-2}: Viagem com documento {documento} e placa {equipamento} já foi comprada anteriormente. Ignorando.")
                    continue

                # Verificação para circulacao
                if situacao == "Circulacao":
                    st.write(f"Linha {i-2}: Preencher Vale-Pedágio")
                    st.write("Fornecedor:", fornecedor)
                    st.write("Projeto:", projeto)
                    st.write("Documento:", documento)
                    st.write("Equipamento:", equipamento)
                    st.write("Tipo de Conjunto:", tipo_conjunto)
                    st.write("Situação:", situacao)

                    # Processar a viagem de acordo com o tipo de conjunto
                    processar_viagem(equipamento, projeto, tipo_conjunto)

                    # Registrar a compra para evitar repetição futura
                    registrar_compra_realizada(documento)
                    st.write("-" * 50)

                elif situacao == "Gerada":
                    st.write(f"Linha {i-2}: Situação GERADA, tentar novamente na próxima iteração.")
                    st.write("-" * 50)
                
                elif situacao == "Finalizada":
                    st.write(f"Linha {i-2}: Situação FINALIZADA, descartando este caminhão.")
                    st.write("-" * 50)

            except AttributeError as e:
                st.write(f"Linha {i-2}: Erro ao capturar informações: {e}")
                st.write("-" * 50)
    else:
        st.write(f"Erro ao acessar a página: {response.status_code}")






# Função para executar o loop de compras
def executar_em_loop():
    global loop_compras_ativo
    while loop_compras_ativo:
        st.write("Iniciando processo de compra em loop...")
        capturar_informacoes(cookies)  # Substitua os cookies por reais
        st.write("Processo concluído. Aguardando 2 minutos antes da próxima execução.")
        time.sleep(120)  # Aguarda 2 minutos

def iniciar_loop():
    global loop_compras_ativo
    loop_compras_ativo = True
    threading.Thread(target=executar_em_loop).start()

def parar_loop():
    global loop_compras_ativo
    loop_compras_ativo = False
# Interface Streamlit
st.title("Sistema de Vale Pedágio - Inserir Cookies")

# Caixa de texto para inserir os cookies
cookies_input = st.text_area("Insira os valores atualizados dos cookies:")

# Estado do botão para começar e parar o processo
processar = st.button("Processar Viagem")
parar = st.button("Parar Execução")

# Verifica se o botão "Processar Viagem" foi pressionado
if processar:
    if cookies_input:
        # Converte a string de cookies para dicionário
        cookies = parse_cookies(cookies_input)
        
        # Captura as informações usando os cookies inseridos
        while True:
            capturar_informacoes(cookies)  # Executa a função principal do seu script
            time.sleep(120) 
    else:
        st.warning("Por favor, insira os cookies antes de processar a viagem.")
# Loop infinito para rodar o script a cada 5 minutos
       
