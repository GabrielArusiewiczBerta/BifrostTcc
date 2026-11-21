// Estimativa de custo ao vivo, mostrada antes de enviar. Só usa textContent (sem HTML injetado).
(function () {
    function fmtNative(value, symbol) {
        if (!value) return 'sem taxa por transação';
        return value.toLocaleString('pt-BR', { maximumFractionDigits: 8 }) + ' ' + symbol;
    }
    function fmtUsd(value) {
        return 'US$ ' + value.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: value < 0.01 ? 6 : 4 });
    }
    function el(tag, text, style) {
        var node = document.createElement(tag);
        if (text) node.textContent = text;
        if (style) node.style.cssText = style;
        return node;
    }

    window.initCostPreview = function (cfg) {
        var panel = document.getElementById(cfg.panelId);
        var submit = document.getElementById(cfg.submitId);
        var form = submit.form;
        var token = form.querySelector('input[name=csrfmiddlewaretoken]').value;
        var timer = null, seq = 0;
        var submitLabel = submit.innerHTML;

        function idle(message, block) {
            panel.replaceChildren(el('span', message, 'color: var(--text-dim);'));
            submit.disabled = !!block;
            submit.innerHTML = submitLabel;
        }

        function render(data) {
            var s = data.selected;
            panel.replaceChildren();
            var head = el('div', null, 'display:flex; justify-content:space-between; flex-wrap:wrap; gap:0.5rem; align-items:baseline;');
            head.appendChild(el('strong', 'Custo estimado antes de enviar', 'color: var(--amber);'));
            var price = s.fee_native ? fmtNative(s.fee_native, s.symbol) + '  (' + fmtUsd(s.fee_usd) + ')' : 'sem taxa por transação';
            head.appendChild(el('span', price, 'font-size:1.15rem; font-weight:700;'));
            panel.appendChild(head);

            var detail = s.fragments + (s.fragments === 1 ? ' transação' : ' transações') + ' · ' + s.onchain_bytes + ' bytes na rede';
            if (s.encrypted) detail += ' (após criptografia)';
            panel.appendChild(el('div', detail, 'color: var(--text-muted); font-size:0.9rem; margin-top:0.35rem;'));

            var units = Object.keys(s.details).map(function (k) { return k + ': ' + s.details[k]; }).join(' · ');
            if (units) panel.appendChild(el('div', units, 'color: var(--text-dim); font-size:0.8rem;'));

            if (!s.feasible) {
                panel.appendChild(el('div', s.note, 'color: var(--amber); margin-top:0.5rem;'));
            }
            var cheapest = data.cheapest;
            if (cheapest && cheapest.blockchain !== s.blockchain && cheapest.fee_usd < s.fee_usd) {
                panel.appendChild(el('div', 'Mais barata para este dado: ' + cheapest.name + ' (' +
                    (cheapest.fee_usd ? fmtUsd(cheapest.fee_usd) : 'sem taxa') + ')', 'color: var(--cyan); font-size:0.85rem; margin-top:0.5rem;'));
            }
            panel.appendChild(el('div', 'Equivalente na mainnet. ' + data.assumptions, 'color: var(--text-dim); font-size:0.75rem; margin-top:0.5rem;'));

            submit.disabled = !s.feasible;
            submit.innerHTML = submitLabel;
            if (s.feasible) {
                var label = s.fee_native ? ' · ' + fmtUsd(s.fee_usd) : ' · sem taxa';
                submit.appendChild(document.createTextNode(label));
            }
        }

        function refresh() {
            var body = cfg.buildBody(form);
            if (!body) { idle(cfg.idleMessage, false); return; }
            var mine = ++seq;
            fetch(cfg.url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
                body: JSON.stringify(body),
            }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, json: j }; }); })
              .then(function (res) {
                  if (mine !== seq) return;
                  if (res.ok) render(res.json); else idle(res.json.message || 'Não foi possível estimar o custo.', true);
              })
              .catch(function () { if (mine === seq) idle('Não foi possível estimar o custo.', true); });
        }

        function schedule() { clearTimeout(timer); timer = setTimeout(refresh, 300); }
        form.addEventListener('input', schedule);
        form.addEventListener('change', schedule);
        idle(cfg.idleMessage, false);
        schedule();
    };
})();
