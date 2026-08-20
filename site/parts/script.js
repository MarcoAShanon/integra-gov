/* =====================================================================
   INTEGRA — comportamento da landing. Sem dependencia externa.

   API consumida pelas fatias (documentada em site/parts/contrato.md):

     .rise                  ganha a classe .in ao entrar na viewport.
                            Atraso opcional: data-atraso="1".."5".
     .bars[data-max]        caixa de grafico. Os filhos .col[data-h]
                            recebem height em % de data-max.
     .proj[data-video]      cartao de video. O <button> interno abre o
                            lightbox; o .poster tambem abre, no mouse.
                            Sem <button>, o cartao e IGNORADO — o botao
                            e o unico acesso por teclado.
     data-video-titulo      nomeia o dialogo daquele video (opcional,
                            mas necessario quando ha mais de um).
     #lightbox-video        id RESERVADO. O elemento e criado por este
                            script; nenhuma fatia escreve essa marcacao.

   Degradacao: com prefers-reduced-motion:reduce, ou sem
   IntersectionObserver, tudo aparece de uma vez e os graficos ja nascem
   preenchidos — nada depende de animacao para ser lido.
   ===================================================================== */
(function () {
  'use strict';

  var ID_LIGHTBOX = 'lightbox-video';

  var parado = !!(window.matchMedia &&
                  window.matchMedia('(prefers-reduced-motion: reduce)').matches);

  function lista(raiz, seletor) {
    if (!raiz || !raiz.querySelectorAll) return [];
    return Array.prototype.slice.call(raiz.querySelectorAll(seletor));
  }

  /* ------------------------------------------------------------------
     Graficos: .bars[data-max] > ... > .col[data-h]
     ------------------------------------------------------------------ */
  function preencherCaixa(caixa) {
    if (!caixa || caixa.getAttribute('data-cheia') === '1') return;
    var max = parseFloat(caixa.getAttribute('data-max'));
    if (!isFinite(max) || max <= 0) return;
    lista(caixa, '.col[data-h]').forEach(function (col) {
      var h = parseFloat(col.getAttribute('data-h'));
      if (!isFinite(h)) return;
      var pct = (h / max) * 100;
      if (pct < 0) pct = 0;
      if (pct > 100) pct = 100;
      /* piso de 2%: uma barra de valor baixo ainda precisa existir. */
      col.style.height = Math.max(2, pct) + '%';
    });
    caixa.setAttribute('data-cheia', '1');
  }

  function preencherEscopo(escopo) {
    if (!escopo) return;
    if (escopo.matches && escopo.matches('.bars[data-max]')) preencherCaixa(escopo);
    lista(escopo, '.bars[data-max]').forEach(preencherCaixa);
  }

  /* ------------------------------------------------------------------
     Entrada por rolagem
     ------------------------------------------------------------------ */
  function revelarTudo() {
    lista(document, '.rise').forEach(function (el) { el.classList.add('in'); });
    preencherEscopo(document);
  }

  function iniciarRevelacao() {
    if (parado || !('IntersectionObserver' in window)) {
      revelarTudo();
      return;
    }
    var observador = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (entrada) {
        if (!entrada.isIntersecting) return;
        entrada.target.classList.add('in');
        preencherEscopo(entrada.target);
        observador.unobserve(entrada.target);
      });
    }, { threshold: 0.15, rootMargin: '0px 0px -6% 0px' });

    lista(document, '.rise, .bars[data-max]').forEach(function (el) {
      observador.observe(el);
    });
  }

  /* ------------------------------------------------------------------
     Lightbox de video: dialogo modal com armadilha de foco e devolucao
     do foco ao elemento que o abriu.
     ------------------------------------------------------------------ */
  function iniciarLightbox() {
    var cartoes = lista(document, '.proj[data-video]');
    if (!cartoes.length) return;   /* sem video, sem dialogo no DOM */

    var lb = document.getElementById(ID_LIGHTBOX);
    if (!lb) {
      lb = document.createElement('div');
      lb.id = ID_LIGHTBOX;
      lb.className = 'lightbox';
      lb.setAttribute('role', 'dialog');
      lb.setAttribute('aria-modal', 'true');
      lb.setAttribute('aria-label', 'Vídeo de execução');
      lb.innerHTML =
        '<button type="button" class="lightbox-fechar" aria-label="Fechar vídeo">✕</button>' +
        '<video class="lightbox-video" controls playsinline preload="none"></video>';
      document.body.appendChild(lb);
    }
    lb.hidden = true;

    var video = lb.querySelector('video');
    var botaoFechar = lb.querySelector('.lightbox-fechar');
    if (!video || !botaoFechar) return;

    var origem = null;
    /* irmaos do dialogo: ficam inertes enquanto ele esta aberto, senao
       o rotor do leitor de tela passeia pela pagina atras dele. A
       armadilha de Tab sozinha nao contem o rotor. */
    var irmaos = Array.prototype.filter.call(document.body.children, function (el) {
      return el !== lb;
    });

    function aberto() { return lb.hidden === false; }

    function trancarFundo(trancar) {
      irmaos.forEach(function (el) {
        if (trancar) {
          el.setAttribute('inert', '');
          el.setAttribute('aria-hidden', 'true');
        } else {
          el.removeAttribute('inert');
          el.removeAttribute('aria-hidden');
        }
      });
    }

    function focaveis() {
      return [botaoFechar, video].filter(function (el) {
        return el && !el.hidden;
      });
    }

    function abrir(src, disparador, titulo) {
      if (!src || aberto()) return;
      origem = disparador || document.activeElement;
      lb.setAttribute('aria-label', titulo || 'Vídeo de execução');
      video.setAttribute('src', src);
      lb.hidden = false;
      trancarFundo(true);
      document.documentElement.style.overflow = 'hidden';
      botaoFechar.focus();
      var p = video.play();
      if (p && typeof p.catch === 'function') { p.catch(function () {}); }
    }

    function fechar() {
      if (!aberto()) return;
      try { video.pause(); } catch (e) { /* navegador sem midia */ }
      video.removeAttribute('src');
      try { video.load(); } catch (e) { /* idem */ }
      lb.hidden = true;
      trancarFundo(false);
      document.documentElement.style.overflow = '';
      if (origem && typeof origem.focus === 'function') origem.focus();
      origem = null;
    }

    /* clique no fundo (nao no video) e no botao fecham */
    lb.addEventListener('click', function (ev) {
      if (ev.target === lb || ev.target === botaoFechar) fechar();
    });

    /* Escape fecha; Tab circula so dentro do dialogo */
    document.addEventListener('keydown', function (ev) {
      if (!aberto()) return;
      if (ev.key === 'Escape' || ev.key === 'Esc') {
        ev.preventDefault();
        fechar();
        return;
      }
      if (ev.key !== 'Tab') return;
      var alvos = focaveis();
      if (!alvos.length) return;
      var primeiro = alvos[0];
      var ultimo = alvos[alvos.length - 1];
      var atual = document.activeElement;
      if (alvos.indexOf(atual) === -1) {
        ev.preventDefault();
        primeiro.focus();
        return;
      }
      if (ev.shiftKey && atual === primeiro) {
        ev.preventDefault();
        ultimo.focus();
      } else if (!ev.shiftKey && atual === ultimo) {
        ev.preventDefault();
        primeiro.focus();
      }
    });

    cartoes.forEach(function (cartao) {
      var src = cartao.getAttribute('data-video');
      var botao = cartao.querySelector('button');
      /* sem <button> nao ha acesso por teclado, e nao haveria para onde
         devolver o foco ao fechar. Ignorar o cartao deixa a falha
         visivel na previa da fatia, em vez de virar defeito silencioso
         de acessibilidade em producao. */
      if (!src || !botao) return;
      var titulo = cartao.getAttribute('data-video-titulo');
      var poster = cartao.querySelector('.poster');

      botao.addEventListener('click', function (ev) {
        ev.preventDefault();
        abrir(src, botao, titulo);
      });
      if (poster) {
        poster.style.cursor = 'pointer';
        poster.addEventListener('click', function (ev) {
          /* o clique no proprio <button> ja foi tratado acima */
          if (ev.target === botao || (botao.contains && botao.contains(ev.target))) return;
          abrir(src, botao, titulo);
        });
      }
    });
  }

  iniciarRevelacao();
  iniciarLightbox();
})();
