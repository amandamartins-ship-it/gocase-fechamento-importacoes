from app.application.use_cases.descobrir_processos import DescobrirProcessosUseCase
from app.domain.entities import Documento, DocumentoRef, Embarque, Processo, TipoDocumento


class DriveRepoFalso:
    def __init__(self, processos):
        self._processos = processos

    def listar_processos(self):
        return self._processos

    def baixar_conteudo(self, drive_file_id):
        raise NotImplementedError


class ProcessoRepoFalso:
    def __init__(self):
        self.salvos = []

    def salvar(self, processo):
        self.salvos.append(processo)
        return processo

    def buscar_por_codigo(self, codigo):
        return next((p for p in self.salvos if p.codigo == codigo), None)

    def listar(self):
        return self.salvos


def _processo_com_documentos(codigo, tipos):
    embarque = Embarque(codigo=f"{codigo}.1", drive_folder_id="f")
    for tipo in tipos:
        embarque.documentos.append(
            Documento(ref=DocumentoRef(drive_file_id="x", nome_arquivo="x", caminho="x"), tipo=tipo)
        )
    processo = Processo(codigo=codigo, empresa_codigo=codigo[:3])
    processo.embarques = [embarque]
    return processo


def test_resumo_conta_processos_embarques_e_documentos_por_tipo():
    processos = [
        _processo_com_documentos("GOC25129", [TipoDocumento.DI, TipoDocumento.NOTA_FISCAL]),
        _processo_com_documentos("BBI25167", [TipoDocumento.DI]),
    ]
    use_case = DescobrirProcessosUseCase(DriveRepoFalso(processos), ProcessoRepoFalso())

    resumo = use_case.executar()

    assert resumo.total_processos == 2
    assert resumo.total_embarques == 2
    assert resumo.total_documentos == 3
    assert resumo.documentos_por_tipo[str(TipoDocumento.DI)] == 2
    assert resumo.documentos_por_tipo[str(TipoDocumento.NOTA_FISCAL)] == 1
    assert set(resumo.processos) == {"GOC25129", "BBI25167"}


def test_resumo_vazio_quando_nenhum_processo_encontrado():
    use_case = DescobrirProcessosUseCase(DriveRepoFalso([]), ProcessoRepoFalso())
    resumo = use_case.executar()
    assert resumo.total_processos == 0
    assert resumo.documentos_por_tipo == {}
