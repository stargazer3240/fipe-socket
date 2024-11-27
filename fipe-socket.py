from dataclasses import dataclass, field
import socket
import ssl
import json
from time import sleep

HOSTNAME = "parallelum.com.br"
PORT = 443
CONTEXT = ssl.create_default_context()


class GETResponse:
    def __init__(self, data: bytes) -> None:
        sep = "\r\n\r\n"
        data_str = data.decode()
        self.header = data_str.partition(sep)[0]
        self.content = data_str.partition(sep)[2]
        self.full_response = data_str
        self.http_status = int(data_str[9:12])

    def __str__(self) -> str:
        return self.full_response


def find_response_length(first_stream: bytes) -> int:
    stream_lines = first_stream.splitlines()
    content_length_line = stream_lines[3]
    content_length = int(content_length_line.removeprefix(b"Content-Length: "))

    sep = b"\r\n\r\n"
    header = first_stream.partition(sep)[0]
    header_length = len(header + sep)
    return content_length + header_length


def get_request(request_path: str) -> GETResponse:
    with socket.socket() as sock:
        sock.connect((HOSTNAME, PORT))
        with CONTEXT.wrap_socket(sock, server_hostname=HOSTNAME) as ssock:
            ssock.sendall(
                b"GET /fipe/api/v1/carros/"
                + request_path.encode()
                + b" HTTP/1.1\nHost: parallelum.com.br\n\n"
            )
            data = ssock.recv()

            message_length = find_response_length(data)
            bytes_received = len(data)
            while bytes_received < message_length:
                chunk = ssock.recv(min(message_length - bytes_received, 1024))
                data += chunk
                bytes_received += len(chunk)
            return GETResponse(data)


def get_marcas() -> GETResponse:
    return get_request("marcas")


def get_modelos(codigo_marca: int) -> GETResponse:
    return get_request(f"marcas/{codigo_marca}/modelos")


def get_anos(codigo_marca: int, codigo_modelo: int) -> GETResponse:
    return get_request(f"marcas/{codigo_marca}/modelos/{codigo_modelo}/anos")


def get_valor(codigo_marca: int, codigo_modelo: int, codigo_ano: str) -> GETResponse:
    return get_request(
        f"marcas/{codigo_marca}/modelos/{codigo_modelo}/anos/{codigo_ano}"
    )


@dataclass
class ResponseObject:
    codigo: int | str = 0
    nome: str = ""


@dataclass
class Veiculo:
    marca: ResponseObject = field(default_factory=ResponseObject)
    modelo: ResponseObject = field(default_factory=ResponseObject)
    ano: ResponseObject = field(default_factory=ResponseObject)


def find_nome_json(codigo_escolhido: int | str, json) -> str:
    for obj in json:
        if type(codigo_escolhido) is int:
            codigo_atual = int(obj["codigo"])
        else:
            codigo_atual = obj["codigo"]
        if codigo_escolhido == codigo_atual:
            return obj["nome"]
    return ""


def menu_marcas() -> None:
    while True:
        print("MARCAS DOS VEÍCULOS:\n")
        print("CÓDIGO\t\tNOME")

        marcas_json = json.loads(get_marcas().content)
        for obj in marcas_json:
            codigo_marca = int(obj["codigo"])
            print(f"{codigo_marca:3}\t\t{obj["nome"]}")

        codigo_escolhido = int(input("\nEscolha uma marca pelo código [0 para sair]: "))
        modelos_response = get_modelos(codigo_escolhido)

        if codigo_escolhido == 0:
            return
        elif modelos_response.http_status == 500:
            print("\nCódigo inválido! Tente novamente\n")
            sleep(3)
        else:
            nome_marca = find_nome_json(codigo_escolhido, marcas_json)
            marca = ResponseObject(codigo_escolhido, nome_marca)
            menu_modelos(Veiculo(marca), modelos_response)


def menu_modelos(v: Veiculo, modelos_response: GETResponse) -> None:
    while True:
        print(f'\nMODELOS DA MARCA "{v.marca.nome}":\n')
        print("CÓDIGO\t\tNOME")

        modelos_json = json.loads(modelos_response.content)
        for obj in modelos_json["modelos"]:
            codigo = int(obj["codigo"])
            print(f"{codigo:5}\t\t{obj["nome"]}")

        codigo_escolhido = int(
            input("\nEscolha um modelo pelo código [0 para retornar]: ")
        )
        anos_response = get_anos(int(v.marca.codigo), int(codigo_escolhido))

        if codigo_escolhido == 0:
            return
        elif anos_response.http_status == 500:
            print("\nCódigo inválido! Tente novamente\n")
            sleep(3)
        else:
            v.modelo.codigo = codigo_escolhido
            v.modelo.nome = find_nome_json(codigo_escolhido, modelos_json["modelos"])
            menu_anos(v, anos_response)
            return


def menu_anos(v: Veiculo, anos_response: GETResponse) -> None:
    while True:
        print(f'\nANOS DO MODELO "{v.modelo.nome}":\n')
        print("ANO\t\tTIPO")
        anos = json.loads(anos_response.content)
        for obj in anos:
            print(f"{obj["codigo"]}\t\t{obj["nome"]}")

        codigo_escolhido = input(
            '\nEscolha um modelo pelo ano (exemplo: "2024-2") [0 para retornar]: '
        )

        valor_response = get_valor(
            int(v.marca.codigo), int(v.modelo.codigo), codigo_escolhido
        )

        if codigo_escolhido == "0":
            return
        elif valor_response.http_status == 500:
            print("\nCódigo inválido! Tente novamente\n")
            sleep(3)
        else:
            v.ano.codigo = codigo_escolhido
            v.ano.nome = find_nome_json(codigo_escolhido, anos)
            menu_veiculos(valor_response)
            return


def menu_veiculos(valor_response: GETResponse) -> None:
    print("\nINFORMAÇÕES:\n")
    object = json.loads(valor_response.content)
    valor = f"Marca: {object["Marca"]}\nModelo: {object["Modelo"]}\nAno: {object["AnoModelo"]}\nCombustível: {object["Combustivel"]}\nData Consulta: {object["MesReferencia"]}\nVALOR: {object["Valor"]}"
    print(valor)
    while True:
        resposta = input(
            '\nDeseja salvar as informações em um arquivo ["sim" para confirmar]? '
        )
        if resposta.upper() in {"S", "SIM"}:
            filename = f"{object["Modelo"]} ({object["AnoModelo"]}) - {object["MesReferencia"]}.txt"
            with open(filename, "w") as f:
                print(valor, file=f)
            print("Arquivo salvo! Voltando para o menu inicial.\n")
            sleep(3)
            return
        else:
            print("Resposta não reconhecida, tente denovo.\n")
            sleep(2)


menu_marcas()
