"""Contrato de dados da ficha financeira — estruturas puras, sem I/O.

Este módulo define **só o formato do resultado**. Ele não lê PDF, não conhece
layout e não aplica regra de negócio: quem lê é :mod:`~integra_gov.
ficha_financeira.leitura`, quem interpreta é o script que consome a ficha.

A ideia central é que a biblioteca devolva o que está **impresso**, sem
traduzir para nenhuma convenção contábil. Por isso:

* o valor é sempre **positivo** e o sinal fica na :class:`Natureza` — guardar
  desconto como negativo embutiria uma escolha que é do consumidor;
* o valor é :class:`~decimal.Decimal`, nunca ``float`` — são centavos, e o
  erro de arredondamento binário quebraria a conferência contra os totais;
* a natureza declarada na ficha (a coluna ``R/D``) fica visível **ao lado** da
  natureza efetiva, porque o SIAPE só imprime essa coluna na linha em que o
  grupo começa (ver :class:`Lancamento`).

Há dois níveis de estrutura, e a separação é proposital:

**Cru** (:class:`LinhaCrua`, :class:`BlocoCru`) — o que os parsers de layout
produzem: exatamente o que estava impresso, sem interpretação. **Final**
(:class:`Lancamento`, :class:`FichaFinanceira`) — o que a conciliação produz a
partir do cru. Sem esse degrau, cada parser teria de resolver a natureza por
conta própria e a conciliação reconstruiria tudo de novo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

__all__ = [
    "Aviso",
    "BlocoCru",
    "CodigoAviso",
    "Competencia",
    "FichaFinanceira",
    "Identificacao",
    "Lancamento",
    "Layout",
    "LinhaCrua",
    "Natureza",
    "Origem",
    "TipoBeneficiario",
    "TotaisMes",
]

#: Abreviações de mês como o SIAPE as imprime, na ordem do calendário.
MESES_SIAPE = ("JAN", "FEV", "MAR", "ABR", "MAI",
               "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ")


def _normalizar_rubrica(codigo: str) -> str:
    """Forma canônica de um código de rubrica, para comparação.

    Descarta espaços e zeros à esquerda (``"00597"`` e ``"597"`` são a mesma
    rubrica), mas um código todo de zeros colapsa para ``"0"``, nunca para
    ``""`` — senão ele casaria com qualquer entrada vazia.
    """
    limpo = codigo.strip()
    if not limpo:
        return ""
    return limpo.lstrip("0") or "0"


class TipoBeneficiario(Enum):
    """Quem é o titular da ficha.

    ``INSTITUIDOR`` é o servidor que originou uma pensão; ``PENSIONISTA`` é
    quem a recebe. Uma ficha de pensionista traz os dois (o instituidor no
    campo ``INST.``), e é por isso que os dois valores existem aqui.
    """

    SERVIDOR = "SERVIDOR"
    APOSENTADO = "APOSENTADO"
    PENSIONISTA = "PENSIONISTA"
    INSTITUIDOR = "INSTITUIDOR"
    DESCONHECIDO = "DESCONHECIDO"


class Natureza(Enum):
    """Se o lançamento entra a favor ou contra o beneficiário.

    ``INDEFINIDA`` não é um terceiro tipo de lançamento: é a admissão honesta
    de que a natureza não pôde ser determinada — a linha veio sem marcador e
    sem grupo anterior no bloco, ou o grupo herdado não sobreviveu à
    conferência contra os totais. Cabe ao consumidor decidir o que fazer.
    """

    RENDIMENTO = "R"
    DESCONTO = "D"
    INDEFINIDA = "?"


class Layout(Enum):
    """De qual impressão o PDF veio.

    ``SIAPE`` é o relatório do mainframe (``L.A54120.DE``), monoespaçado, seis
    meses por página. ``ESIAPE`` é a impressão web do e-SIAPE, em tabela, com
    um semestre por bloco.
    """

    SIAPE = "SIAPE"
    ESIAPE = "ESIAPE"


@dataclass(frozen=True, order=True)
class Competencia:
    """Mês de referência de um lançamento (ano + mês, sem dia).

    Ordenável e hasheável, para servir de chave de agrupamento e de eixo de
    ordenação sem que o consumidor precise montar tuplas na mão.

    Attributes:
        ano: ano com quatro dígitos.
        mes: mês de 1 a 12.

    Raises:
        ValueError: se ``mes`` estiver fora de 1–12.
    """

    ano: int
    mes: int

    def __post_init__(self) -> None:
        if not 1 <= self.mes <= 12:
            raise ValueError(f"mês fora de 1–12: {self.mes!r}")
        # Ano de dois dígitos ordenaria antes de qualquer ficha real e
        # corromperia a comparação entre exercícios sem dar sinal nenhum.
        if not 1000 <= self.ano <= 9999:
            raise ValueError(f"ano deve ter quatro dígitos: {self.ano!r}")

    @classmethod
    def de_texto(cls, mes: str, ano: int) -> Competencia:
        """Constrói a partir da abreviação impressa no cabeçalho da tabela.

        Args:
            mes: abreviação de três letras (``"JAN"`` … ``"DEZ"``), sem
                sensibilidade a caixa ou espaços em volta.
            ano: ano com quatro dígitos.

        Raises:
            ValueError: se a abreviação não for reconhecida.
        """
        chave = mes.strip().upper()
        try:
            numero = MESES_SIAPE.index(chave) + 1
        except ValueError:
            raise ValueError(f"mês não reconhecido: {mes!r}") from None
        return cls(ano=ano, mes=numero)

    @property
    def sigla(self) -> str:
        """A abreviação de três letras correspondente (``"JUN"``)."""
        return MESES_SIAPE[self.mes - 1]

    def __str__(self) -> str:
        return f"{self.ano:04d}-{self.mes:02d}"


@dataclass(frozen=True)
class Aviso:
    """Divergência encontrada sem interromper a leitura.

    O código é **estável** para permitir decisão programática: o consumidor
    faz ``if any(a.codigo == "MES_NAO_CONFERE" for a in ficha.avisos)`` em vez
    de casar substring de mensagem, que quebra a cada ajuste de texto.

    Attributes:
        codigo: identificador estável (ver :class:`CodigoAviso`).
        mensagem: descrição legível, para log e para o humano.
        competencia: mês a que a divergência se refere, quando aplicável.
    """

    codigo: str
    mensagem: str
    competencia: Competencia | None = None

    def to_dict(self) -> dict:
        """Versão serializável em JSON."""
        return {
            "codigo": self.codigo,
            "mensagem": self.mensagem,
            "competencia": (None if self.competencia is None
                            else str(self.competencia)),
        }


class CodigoAviso:
    """Códigos estáveis usados em :class:`Aviso`.

    São constantes de texto (e não um ``Enum``) para que o valor sobreviva a
    serialização e comparação simples do lado do consumidor.
    """

    #: A soma dos lançamentos do mês não reproduz os totais impressos.
    MES_NAO_CONFERE = "MES_NAO_CONFERE"
    #: Linha sem marcador ``R/D`` e sem grupo anterior no bloco.
    NATUREZA_INDEFINIDA = "NATUREZA_INDEFINIDA"
    #: O bloco não trouxe as linhas de total para conferir.
    TOTAIS_AUSENTES = "TOTAIS_AUSENTES"
    #: Alguma página do intervalo desta ficha não pôde ser extraída, então a
    #: ficha pode estar incompleta — ver :attr:`PaginaTexto.erro`.
    PAGINA_ILEGIVEL = "PAGINA_ILEGIVEL"


@dataclass(frozen=True)
class Lancamento:
    """Uma rubrica lançada em um mês.

    Sobre a coluna ``R/D``: a ficha **não** a imprime em toda linha. O
    marcador aparece na linha em que o grupo começa e as linhas seguintes o
    herdam, na ordem impressa. Por isso a natureza efetiva pode ter vindo por
    herança — o que é registrado em :attr:`natureza_inferida`, derivado, e não
    em campo próprio (campo armazenado poderia divergir do resto do estado).

    Attributes:
        rubrica: código da rubrica como impresso, com os zeros à esquerda
            preservados (``"00597"``). É texto, não inteiro: o zero à esquerda
            faz parte do código no SIAPE.
        descricao: descrição como impressa. No relatório do mainframe o campo
            tem 26 caracteres e o próprio SIAPE **trunca** o nome da rubrica
            (``"PENSAO COMPLEMENTAR - CIVI"``); a biblioteca não completa o
            que não foi impresso.
        competencia: mês/ano do lançamento.
        valor: sempre **positivo**; o sentido está em ``natureza``.
        natureza: natureza efetiva, já resolvida.
        natureza_declarada: o caractere lido na coluna ``R/D`` (``"R"``,
            ``"D"``) ou ``None`` quando a linha o herdou do grupo.
        sequencia: a coluna ``SEQ`` da ficha, quando presente.
    """

    rubrica: str
    descricao: str
    competencia: Competencia
    valor: Decimal
    natureza: Natureza
    natureza_declarada: str | None = None
    sequencia: int | None = None

    def __post_init__(self) -> None:
        if self.valor < 0:
            raise ValueError(
                f"valor deve ser positivo (o sinal é a natureza): {self.valor}")
        if self.natureza_declarada is None:
            return
        if self.natureza_declarada not in ("R", "D"):
            raise ValueError(
                f"marcador R/D inválido: {self.natureza_declarada!r} "
                f"(esperado 'R', 'D' ou None)")
        # Marcador impresso é definitivo: a natureza efetiva não pode
        # contradizê-lo, nem ficar indefinida. Indefinida existe só para a
        # linha que veio SEM marcador e sem grupo anterior.
        if self.natureza.value != self.natureza_declarada:
            raise ValueError(
                f"natureza {self.natureza.value!r} contradiz o marcador "
                f"impresso {self.natureza_declarada!r}")

    @property
    def natureza_inferida(self) -> bool:
        """``True`` quando a natureza veio por herança, não impressa na linha."""
        return (self.natureza_declarada is None
                and self.natureza is not Natureza.INDEFINIDA)

    @property
    def e_rendimento(self) -> bool:
        """Atalho de leitura; ``False`` também quando a natureza é indefinida."""
        return self.natureza is Natureza.RENDIMENTO

    @property
    def e_desconto(self) -> bool:
        """Atalho de leitura; ``False`` também quando a natureza é indefinida."""
        return self.natureza is Natureza.DESCONTO

    def to_dict(self) -> dict:
        """Versão serializável em JSON (``Decimal`` vira texto)."""
        return {
            "rubrica": self.rubrica,
            "descricao": self.descricao,
            "competencia": str(self.competencia),
            "ano": self.competencia.ano,
            "mes": self.competencia.mes,
            "valor": str(self.valor),
            "natureza": self.natureza.value,
            "natureza_declarada": self.natureza_declarada,
            "natureza_inferida": self.natureza_inferida,
            "sequencia": self.sequencia,
        }


@dataclass(frozen=True)
class TotaisMes:
    """Os totais que a **própria ficha** imprime para um mês.

    Guardados como vieram, sem recálculo: eles são a referência contra a qual
    os lançamentos lidos são conferidos. ``None`` significa linha em branco na
    ficha, que é diferente de zero impresso — e a distinção importa, porque um
    mês sem descontos imprime a linha vazia, não ``0,00``.

    Attributes:
        competencia: mês/ano a que os totais se referem.
        bruto: linha ``TOTAL BRUTO``.
        descontos: linha ``TOTAL DESCONTOS``.
        liquido: linha ``TOTAL LIQUIDO``.
        confere: ``True`` quando a soma dos lançamentos do mês reproduz os
            totais impressos. ``False`` é o sinal de que a leitura daquele mês
            não é confiável — não de que a ficha está errada.

            **Não tem default, de propósito.** Este tipo também é usado em
            :attr:`BlocoCru.totais_lidos`, *antes* de qualquer conferência; um
            default ``True`` faria o estado não-validado nascer parecendo
            validado, e bastaria a conciliação esquecer um caminho para a
            ficha declarar uma consistência que ninguém verificou. Sem default,
            todo construtor é obrigado a se posicionar. No nível cru o valor é
            sempre ``False``: "ainda não conferido" e "não fechou" são
            deliberadamente o mesmo bit, porque os dois querem dizer *não
            confie neste mês*.
    """

    competencia: Competencia
    bruto: Decimal | None
    descontos: Decimal | None
    liquido: Decimal | None
    confere: bool

    def to_dict(self) -> dict:
        """Versão serializável em JSON (``Decimal`` vira texto)."""
        return {
            "competencia": str(self.competencia),
            "bruto": None if self.bruto is None else str(self.bruto),
            "descontos": None if self.descontos is None else str(self.descontos),
            "liquido": None if self.liquido is None else str(self.liquido),
            "confere": self.confere,
        }


@dataclass(frozen=True)
class Identificacao:
    """Cabeçalho da ficha: de quem ela é e de onde vem.

    Todos os campos são opcionais porque nem todo layout imprime todos eles —
    ``instituidor_*``, por exemplo, só existe em ficha de pensão, e
    ``situacao`` só aparece na impressão web. Campo ausente vira ``None``,
    nunca string vazia, para distinguir "não impresso" de "impresso em
    branco".

    ``situacao`` guarda o literal como impresso (``"02 - APOSENTADO"``), que é
    a fonte de que ``tipo`` foi derivado no layout do e-SIAPE; preservá-lo
    evita perder informação numa tradução para enum.
    """

    tipo: TipoBeneficiario = TipoBeneficiario.DESCONHECIDO
    matricula: str | None = None
    nome: str | None = None
    situacao: str | None = None
    orgao_codigo: str | None = None
    orgao_nome: str | None = None
    upag_codigo: str | None = None
    upag_nome: str | None = None
    instituidor_matricula: str | None = None
    instituidor_nome: str | None = None
    banco: str | None = None
    agencia: str | None = None
    conta: str | None = None

    @property
    def chave(self) -> tuple:
        """Identidade para segmentar um PDF mesclado (ver :class:`BlocoCru`)."""
        return (self.tipo, self.matricula, self.orgao_codigo)

    def to_dict(self) -> dict:
        """Versão serializável em JSON."""
        return {
            "tipo": self.tipo.value,
            "matricula": self.matricula,
            "nome": self.nome,
            "situacao": self.situacao,
            "orgao_codigo": self.orgao_codigo,
            "orgao_nome": self.orgao_nome,
            "upag_codigo": self.upag_codigo,
            "upag_nome": self.upag_nome,
            "instituidor_matricula": self.instituidor_matricula,
            "instituidor_nome": self.instituidor_nome,
            "banco": self.banco,
            "agencia": self.agencia,
            "conta": self.conta,
        }


@dataclass(frozen=True)
class Origem:
    """De onde a ficha foi lida — rastreabilidade da leitura.

    Attributes:
        layout: qual impressão foi reconhecida.
        arquivo: caminho do PDF, quando a leitura veio de um arquivo.
        paginas: números das páginas do PDF que compõem esta ficha (1-based).
            Um PDF mesclado gera várias fichas, e é este campo que diz de onde
            cada uma saiu.
    """

    layout: Layout
    arquivo: str | None = None
    paginas: tuple[int, ...] = ()

    def to_dict(self) -> dict:
        """Versão serializável em JSON."""
        return {
            "layout": self.layout.value,
            "arquivo": self.arquivo,
            "paginas": list(self.paginas),
        }


# --------------------------------------------------------------------------
# Nível cru — o que os parsers de layout produzem, antes da conciliação
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class LinhaCrua:
    """Uma linha da tabela, exatamente como impressa.

    Sem natureza resolvida e sem valor interpretado além da conversão de
    ``"1.931,56"`` para :class:`~decimal.Decimal`. Uma linha cobre vários
    meses (as colunas do bloco), e só as células preenchidas entram em
    ``valores``.

    Attributes:
        rubrica: código como impresso.
        descricao: descrição como impressa.
        natureza_declarada: o caractere da coluna ``R/D``, ou ``None`` se a
            célula veio em branco (a linha herda o grupo anterior).
        sequencia: a coluna ``SEQ``, quando presente.
        valores: pares ``(competência, valor)`` das células preenchidas.
        tabela: identificador do **bloco impresso de tabela** de onde a linha
            veio. No formato A é o número da página (uma tabela por página);
            no formato B é um contador sequencial, porque uma página traz dois
            blocos (um por semestre).

            É **proveniência**, usada em mensagens de diagnóstico — não um
            limite de herança. O campo nasceu para marcar a quebra em que o
            grupo ``R/D`` seria reaberto, mas a evidência derrubou essa regra:
            o grupo atravessa a quebra de tabela, e quem decide isso é
            :func:`~integra_gov.ficha_financeira.conciliacao.conciliar`, sem
            depender deste campo. A proveniência por **página** mora em
            :attr:`BlocoCru.paginas` e :attr:`Origem.paginas`.
    """

    rubrica: str
    descricao: str
    natureza_declarada: str | None = None
    sequencia: int | None = None
    valores: tuple[tuple[Competencia, Decimal], ...] = ()
    tabela: int | None = None


@dataclass(frozen=True)
class BlocoCru:
    """Um bloco contíguo de páginas com a mesma identidade e o mesmo exercício.

    Esta é a unidade que a conciliação transforma em :class:`FichaFinanceira`.
    Ela existe porque os PDFs que o próprio pacote produz são **mesclados**:
    :class:`~integra_gov.esiape.ficha_anual.FichaAnualServidor` junta blocos de
    até 15 anos num único arquivo e
    :class:`~integra_gov.esiape.ficha_multi_orgao.FichaMultiOrgao` junta vários
    órgãos — com matrícula e órgão mudando de uma página para outra. Ler esse
    arquivo como "uma ficha" misturaria identidades diferentes.

    Attributes:
        identificacao: cabeçalho comum às páginas do bloco.
        exercicio: ano a que o bloco se refere (o do título, não o da emissão).
        competencias: meses cobertos, na ordem impressa no cabeçalho.
        linhas: as linhas da tabela, na ordem impressa — a ordem importa,
            porque o marcador ``R/D`` é herdado do grupo anterior.
        totais_lidos: as linhas de total, como impressas. Chegam aqui sempre
            com ``confere=False`` **por definição** — quem confere é a
            conciliação, e neste ponto ela ainda não rodou. Não interprete um
            ``False`` daqui como "mês já reprovado" nem pule a conferência
            dele achando que já foi feita.
        emitido_em: data de emissão do relatório, quando impressa.
        paginas: números das páginas do PDF que formam o bloco (1-based).
    """

    identificacao: Identificacao
    exercicio: int
    competencias: tuple[Competencia, ...] = ()
    linhas: tuple[LinhaCrua, ...] = ()
    totais_lidos: tuple[TotaisMes, ...] = ()
    emitido_em: date | None = None
    paginas: tuple[int, ...] = ()


# --------------------------------------------------------------------------
# Nível final — o que a biblioteca devolve
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class FichaFinanceira:
    """Uma ficha financeira: uma identidade, um exercício.

    É a unidade de retorno da biblioteca. Um PDF mesclado devolve **várias**
    — por isso a API principal é plural
    (:func:`~integra_gov.ficha_financeira.ler_fichas_financeiras`).

    Os métodos abaixo são **consultas de leitura**, atalhos para não obrigar
    cada script a reescrever o mesmo ``for``; nenhum deles decide regra de
    negócio.

    Attributes:
        identificacao: cabeçalho da ficha.
        exercicio: ano a que a ficha se refere (o do título, não o da emissão).
        lancamentos: todos os lançamentos, na ordem em que foram lidos.
        totais: os totais impressos, um por mês presente na ficha.
        emitido_em: data de emissão do relatório, quando impressa. Importa
            para quem confere pagamento: diz de quando é a foto.
        origem: rastreabilidade da leitura.
        avisos: divergências encontradas sem interromper a leitura. Ficha com
            aviso é ficha para conferir, não para descartar em silêncio.
    """

    identificacao: Identificacao
    exercicio: int
    lancamentos: tuple[Lancamento, ...] = ()
    totais: tuple[TotaisMes, ...] = ()
    emitido_em: date | None = None
    origem: Origem | None = None
    avisos: tuple[Aviso, ...] = ()

    @property
    def consistente(self) -> bool:
        """``True`` quando todos os meses conferiram e não houve aviso.

        É o gate de uma checagem só: ``if ficha.consistente:``. ``False`` não
        quer dizer que a ficha está errada — quer dizer que a **leitura** não
        se autoconfirmou e alguém precisa olhar.
        """
        return not self.avisos and all(t.confere for t in self.totais)

    def rubricas(self) -> tuple[str, ...]:
        """Códigos de rubrica distintos, em ordem crescente."""
        return tuple(sorted({lanc.rubrica for lanc in self.lancamentos}))

    def competencias(self) -> tuple[Competencia, ...]:
        """Competências distintas com lançamento, em ordem cronológica."""
        return tuple(sorted({lanc.competencia for lanc in self.lancamentos}))

    def por_rubrica(self, rubrica: str) -> tuple[Lancamento, ...]:
        """Lançamentos de uma rubrica, em ordem cronológica.

        Args:
            rubrica: o código como impresso (``"00597"``). A comparação
                normaliza espaços e zeros à esquerda, então ``"597"`` também
                encontra ``"00597"``. Entrada vazia devolve ``()`` — nunca
                casa por acidente com uma rubrica toda de zeros.
        """
        alvo = _normalizar_rubrica(rubrica)
        if not alvo:
            return ()
        return tuple(sorted(
            (lanc for lanc in self.lancamentos
             if _normalizar_rubrica(lanc.rubrica) == alvo),
            key=lambda lanc: lanc.competencia,
        ))

    def por_competencia(self, ano: int, mes: int) -> tuple[Lancamento, ...]:
        """Lançamentos de um mês, na ordem em que foram lidos.

        Args:
            ano: ano com quatro dígitos.
            mes: mês de 1 a 12.
        """
        alvo = Competencia(ano=ano, mes=mes)
        return tuple(lanc for lanc in self.lancamentos
                     if lanc.competencia == alvo)

    def por_natureza(self, natureza: Natureza) -> tuple[Lancamento, ...]:
        """Lançamentos de uma natureza (rendimento, desconto ou indefinida)."""
        return tuple(lanc for lanc in self.lancamentos
                     if lanc.natureza is natureza)

    def totais_de(self, ano: int, mes: int) -> TotaisMes | None:
        """Os totais impressos de um mês, ou ``None`` se o mês não está na ficha."""
        alvo = Competencia(ano=ano, mes=mes)
        for total in self.totais:
            if total.competencia == alvo:
                return total
        return None

    def total_por_rubrica(self) -> dict[str, Decimal]:
        """Soma dos valores de cada rubrica, sem distinguir natureza.

        Somar rendimento com desconto raramente é o que se quer, então o
        agrupamento por natureza fica com o consumidor — use
        :meth:`por_natureza` antes, se for o caso.
        """
        acumulado: dict[str, Decimal] = {}
        for lanc in self.lancamentos:
            acumulado[lanc.rubrica] = acumulado.get(lanc.rubrica, Decimal(0)) + lanc.valor
        return acumulado

    def to_dict(self) -> dict:
        """A ficha inteira como estrutura serializável em JSON."""
        return {
            "identificacao": self.identificacao.to_dict(),
            "exercicio": self.exercicio,
            "lancamentos": [lanc.to_dict() for lanc in self.lancamentos],
            "totais": [total.to_dict() for total in self.totais],
            "emitido_em": (None if self.emitido_em is None
                           else self.emitido_em.isoformat()),
            "origem": None if self.origem is None else self.origem.to_dict(),
            "avisos": [aviso.to_dict() for aviso in self.avisos],
            "consistente": self.consistente,
        }
