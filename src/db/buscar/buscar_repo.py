"""Busca em prontuários: híbrida (full-text ts_rank + vetorial via LangChain)."""

from src.db.models import ResultadoBusca, ResultadoVetorial
from src.db.repos.base import RepositorioBase
from src.db.vectorstore import obter_vectorstore

LIMITE_PADRAO_BUSCA = 10


class BuscaRepositorio(RepositorioBase):
    def buscar_texto(
        self,
        termo: str,
        condicao: str | None = None,
        limite: int = LIMITE_PADRAO_BUSCA,
    ) -> list[ResultadoBusca]:
        filtro = "AND c.nome = %(condicao)s" if condicao else ""
        sql = f"""
            SELECT
                a.id            AS atendimento_id,
                a.paciente_id,
                c.nome          AS condicao,
                e.nome          AS especialidade_principal,
                a.data_atendimento,
                a.queixa,
                a.conduta,
                ts_rank(a.busca, consulta) AS relevancia
            FROM atendimentos a
            JOIN condicoes c ON c.id = a.condicao_id
            JOIN profissionais pr ON pr.id = a.profissional_id
            JOIN especialidades e ON e.id = pr.especialidade_principal_id,
                 plainto_tsquery('portuguese', %(termo)s) AS consulta
            WHERE a.busca @@ consulta {filtro}
            ORDER BY relevancia DESC
            LIMIT %(limite)s
        """
        parametros: dict[str, object] = {"termo": termo, "limite": limite}
        if condicao:
            parametros["condicao"] = condicao
        with self._abrir() as con:
            linhas = con.execute(sql, parametros).fetchall()
        return [ResultadoBusca(**linha) for linha in linhas]

    def buscar_vetorial(
        self,
        consulta: str,
        provedor,
        k: int = 5,
        condicao: str | None = None,
        especialidade: str | None = None,
    ) -> list[ResultadoVetorial]:
        """Busca por similaridade semântica sobre os vetores ingestados via PGVector.

        A busca é feita sobre a coleção do provedor; filtros opcionais por condição
        e especialidade são aplicados via metadados (JSONB) do vector store.
        """

        vetorstore = obter_vectorstore(provedor, dsn=self._dsn)
        filtro: dict[str, str] = {}
        if condicao:
            filtro["condicao"] = condicao
        if especialidade:
            filtro["especialidade_principal"] = especialidade

        pares = vetorstore.similarity_search_with_score(
            consulta, k=k, filter=filtro or None
        )
        resultados = []
        for documento, distancia in pares:
            meta = documento.metadata
            resultados.append(
                ResultadoVetorial(
                    atendimento_id=int(meta["atendimento_id"]),
                    paciente_id=int(meta["paciente_id"]),
                    ordem_chunk=int(meta["ordem_chunk"]),
                    similaridade=round(1.0 - float(distancia), 4),
                    conteudo=documento.page_content,
                    condicao=meta.get("condicao", ""),
                    especialidade_principal=meta.get("especialidade_principal", ""),
                    data_atendimento=meta.get("data_atendimento"),
                )
            )
        return resultados