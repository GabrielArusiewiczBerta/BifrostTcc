// Progresso real fragmento a fragmento (FR10), reutilizado por Store e Migrate. Intercepta o
// envio do formulário e grava cada transação com uma chamada por vez, atualizando a barra com o
// progresso reportado pelo servidor. Se o JavaScript estiver desabilitado, o formulário cai no
// envio síncrono tradicional (sem barra).
(function () {
    function el(tag, text, style, cls) {
        var node = document.createElement(tag);
        if (text) node.textContent = text;
        if (style) node.style.cssText = style;
        if (cls) node.className = cls;
        return node;
    }

    window.progressFlowHelpers = { el: el };

    window.initProgressFlow = function (cfg) {
        var submit = document.getElementById(cfg.submitId);
        var form = submit.form;
        var token = form.querySelector('input[name=csrfmiddlewaretoken]').value;
        var progressPanel = document.getElementById(cfg.progressId);
        var resultPanel = document.getElementById(cfg.resultId);
        var submitLabel = submit.innerHTML;

        function post(url, body) {
            return fetch(url, {
                method: 'POST',
                headers: Object.assign({ 'X-CSRFToken': token }, body ? { 'Content-Type': 'application/json' } : {}),
                body: body ? JSON.stringify(body) : undefined,
            }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, json: j }; }); });
        }

        function showBar(progress, total, label) {
            var pct = total ? Math.round(100 * progress / total) : 0;
            progressPanel.style.display = 'block';
            progressPanel.replaceChildren();
            progressPanel.appendChild(el('div', label, 'margin-bottom: 0.5rem; color: var(--cyan); font-weight: 600;'));
            var track = el('div', null, 'background: rgba(255,255,255,0.08); border-radius: 6px; height: 10px; overflow: hidden;');
            track.appendChild(el('div', null, 'width: ' + pct + '%; height: 10px; background: var(--cyan); transition: width 0.15s ease;'));
            progressPanel.appendChild(track);
            progressPanel.appendChild(el('div', progress + ' / ' + total + ' transações gravadas', 'margin-top: 0.4rem; font-size: 0.8rem; color: var(--text-dim);'));
        }

        function fail(message) {
            progressPanel.style.display = 'block';
            progressPanel.replaceChildren(el('div', message, 'color: var(--rose, #f43f5e);'));
            submit.disabled = false;
            submit.innerHTML = submitLabel;
        }

        function finish(d) {
            progressPanel.style.display = 'none';
            submit.disabled = false;
            submit.innerHTML = submitLabel;
            resultPanel.replaceChildren(cfg.renderResult(d));
        }

        function step() {
            post(cfg.stepUrl).then(function (res) {
                if (!res.ok) { fail(res.json.message || 'Falha ao gravar um fragmento.'); return; }
                var d = res.json;
                if (d.done) {
                    finish(d);
                } else {
                    showBar(d.progress, d.total, cfg.stepLabel(d));
                    step();
                }
            }).catch(function () { fail('Falha ao gravar um fragmento. Tente novamente.'); });
        }

        form.addEventListener('submit', function (e) {
            var body = cfg.buildStartBody(form);
            if (!body) return; // deixa o form validar normalmente (ex.: campo obrigatório vazio)
            e.preventDefault();

            resultPanel.replaceChildren();
            submit.disabled = true;
            submit.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Iniciando...';
            showBar(0, 1, 'Preparando fragmentos...');

            post(cfg.startUrl, body).then(function (res) {
                if (!res.ok) { fail(res.json.message || 'Não foi possível iniciar a operação.'); return; }
                showBar(0, res.json.total, cfg.stepLabel({ progress: 0, total: res.json.total }));
                step();
            }).catch(function () { fail('Não foi possível iniciar a operação.'); });
        });
    };
})();
