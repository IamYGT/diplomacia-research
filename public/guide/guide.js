/* Diplomacia Interactive Master Guide */
(function () {
  'use strict';

  const FLOW_DETAILS = {
    register: 'Kayıt → e-posta doğrulama → ülke/bağımsız bölge seçimi. İlk karar kalıcı etki: vergi, savaş erişimi, fabrika bölgesi.',
    class: 'Sınıf seçimi (Kalemiye, Asker vb.) kalıcı bonus verir. Kalemiye: +%20 elmas fabrikası, +%10 kaynak fabrikası, +50 kışla becerisi.',
    tutorial: 'POST /players/complete-step 0→5: yeni hesapta ~200–250k altın tek sefer. Replay kapalı.',
    quests: 'POST /quests/{quest_key}/claim — work_1 (+5k), work_3 (+20k), work_5 (+50k). UUID ile değil quest_key kullan.',
    factory: 'Elmas fabrikası kur (10k elmas) veya mevcut fabrikaya join. POST /factories/work ile ~2.404 altın / döngü.',
    pills: 'Sağlık biterse POST /players/use-pills. Hap cooldown ~10 dk — farm döngüsünün darboğazı.',
    daily: 'POST /players/daily-claim — günlük ödül. Çift claim / race kapalı.',
    auto: 'POST /auto/toggle — premium gerektirir (normal hesap 403). Manuel work döngüsü şart.',
    politics: 'Parti kur/katıl, seçim, parlamento teklifleri. Uzun vadeli güç — kısa vadeli altın değil.',
    war: 'POST /wars/{id}/contribute — birim gönder. Otomatik savaş: /auto/war (premium).',
    market: 'POST /market/listing + buy. Kendi listingini alamazsın; fiyat validasyonu var.',
    social: 'Socket.IO: global_message, dm_message, country_announcement. Gazete yaz → itibar.'
  };

  const MODULES = {
    players: { title: 'players', desc: 'Profil, bakiye, daily-claim, complete-step, use-pills, skills, diamonds/IAP, tutorial-done' },
    factories: { title: 'factories', desc: 'build, join, work, withdraw, fire, close, work-status — ekonomi çekirdeği' },
    quests: { title: 'quests', desc: 'Liste + POST /quests/{quest_key}/claim — onboarding görevleri' },
    wars: { title: 'wars', desc: 'Liste, detay, contribute, ceasefire — eyalet bazlı savaş' },
    parties: { title: 'parties', desc: 'Parti CRUD, üyelik, seçim adaylığı' },
    parliament: { title: 'parliament', desc: 'Teklifler, oylama, veto, vergi ayarları' },
    market: { title: 'market', desc: 'Listing, buy, cancel — oyuncular arası ticaret' },
    transfer: { title: 'transfer', desc: 'Oyuncular arası altın (min tutar, level gate)' },
    provinces: { title: 'provinces', desc: 'Eyalet bilgisi, hazine deposit, kaynak limitleri' },
    auto: { title: 'auto', desc: 'auto/work, auto/war, craft-pills — premium otomasyon' },
    newspapers: { title: 'newspapers', desc: 'Gazete yazıları, abone, beğeni' },
    messages: { title: 'messages', desc: 'DM REST + Socket.IO dm_message/dm_send' },
    cabinet: { title: 'cabinet', desc: 'Kabine rolleri: president, foreign_affairs vb.' },
    citizenship: { title: 'citizenship', desc: 'Vatandaşlık başvurusu, vize' },
    honor: { title: 'honor', desc: 'İtibar sistemi, claim-honor-premium (kapalı)' },
    mod: { title: 'mod', desc: 'Moderasyon — normal kullanıcı 403' }
  };

  const CLASS_BONUSES = {
    kalemiye: { name: 'Kalemiye', emoji: '📜', work: '+20% elmas fabrikası', resource: '+10% kaynak fabrikası', mil: '+50 kışla becerisi', tip: 'Ekonomi odaklı — maksimum verim için önerilir' },
    asker: { name: 'Asker', emoji: '⚔️', work: 'Savaş birimi bonusları', resource: 'Kışla/eğitim avantajı', mil: 'Yüksek askeri katkı', tip: 'Savaş ve fetih odaklı' },
    diplomat: { name: 'Diplomat', emoji: '🤝', work: 'Ticaret/diplomasi bonusları', resource: 'Transfer/ittifak', mil: 'Orta', tip: 'Sosyal ve siyasi güç' },
    default: { name: 'Diğer', emoji: '🎭', work: 'Sınıfa özel', resource: 'Wiki kontrol', mil: 'Değişken', tip: 'Kayıt sonrası wiki\'den doğrula' }
  };

  // Sidebar scroll spy
  const sections = document.querySelectorAll('section[id]');
  const navLinks = document.querySelectorAll('.sidebar a[href^="#"]');

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          navLinks.forEach((a) => {
            a.classList.toggle('active', a.getAttribute('href') === '#' + e.target.id);
          });
          e.target.classList.add('visible');
        }
      });
    },
    { rootMargin: '-20% 0px -60% 0px', threshold: 0 }
  );
  sections.forEach((s) => observer.observe(s));

  // Mobile menu
  const toggle = document.getElementById('menuToggle');
  const sidebar = document.querySelector('.sidebar');
  if (toggle && sidebar) {
    toggle.addEventListener('click', () => sidebar.classList.toggle('open'));
    navLinks.forEach((a) => a.addEventListener('click', () => sidebar.classList.remove('open')));
  }

  // Flow nodes
  document.querySelectorAll('.flow-node').forEach((node) => {
    node.addEventListener('click', () => {
      document.querySelectorAll('.flow-node').forEach((n) => n.classList.remove('active'));
      node.classList.add('active');
      const key = node.dataset.flow;
      const el = document.getElementById('flowDetail');
      if (el && FLOW_DETAILS[key]) el.textContent = FLOW_DETAILS[key];
    });
  });
  const firstFlow = document.querySelector('.flow-node');
  if (firstFlow) firstFlow.click();

  // Module chips
  document.querySelectorAll('.module-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('.module-chip').forEach((c) => c.classList.remove('active'));
      chip.classList.add('active');
      const m = MODULES[chip.dataset.module];
      const el = document.getElementById('moduleDetail');
      if (el && m) {
        el.innerHTML = '<strong>' + m.title + '</strong><br>' + m.desc;
      }
    });
  });

  // Class cards
  document.querySelectorAll('.class-card').forEach((card) => {
    card.addEventListener('click', () => {
      document.querySelectorAll('.class-card').forEach((c) => c.classList.remove('selected'));
      card.classList.add('selected');
      const key = card.dataset.class || 'default';
      const b = CLASS_BONUSES[key] || CLASS_BONUSES.default;
      const el = document.getElementById('classDetail');
      if (el) {
        el.innerHTML =
          '<h4>' + b.emoji + ' ' + b.name + '</h4>' +
          '<p><strong>Çalışma:</strong> ' + b.work + '</p>' +
          '<p><strong>Kaynak:</strong> ' + b.resource + '</p>' +
          '<p><strong>Askeri:</strong> ' + b.mil + '</p>' +
          '<p class="alert alert-gold" style="margin-top:.75rem">' + b.tip + '</p>';
      }
    });
  });
  const firstClass = document.querySelector('.class-card');
  if (firstClass) firstClass.click();

  function formatReward(item) {
    if (item.reward) return item.reward;
    if (item.reward_gold != null) {
      return '+' + Number(item.reward_gold).toLocaleString('tr-TR') + ' altın';
    }
    return '';
  }

  function bindQuestItems() {
    document.querySelectorAll('.quest-item').forEach((item) => {
      item.addEventListener('click', () => {
        item.classList.toggle('done');
        const fill = item.querySelector('.progress-fill');
        if (fill) fill.style.width = item.classList.contains('done') ? '100%' : '0%';
        updateQuestTotal();
      });
    });
    updateQuestTotal();
  }

  function renderQuestList(checklist) {
    const list = document.getElementById('questList');
    if (!list || !checklist || !checklist.length) return;
    list.innerHTML = checklist.map((item) => {
      const reward = formatReward(item);
      return (
        '<li class="quest-item">' +
        '<div class="quest-top"><span>' + item.label + '</span>' +
        '<span class="quest-reward">' + reward + '</span></div>' +
        '<div class="progress-bar"><div class="progress-fill"></div></div></li>'
      );
    }).join('');
    bindQuestItems();
  }

  function updateQuestTotal() {
    const done = document.querySelectorAll('.quest-item.done').length;
    const total = document.querySelectorAll('.quest-item').length;
    const el = document.getElementById('questTotal');
    if (el) el.textContent = done + ' / ' + total + ' tamamlandı';
  }

  // Checklist persistence
  const STORAGE_KEY = 'diplomacia-guide-checklist';
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'); } catch (e) { saved = {}; }

  document.querySelectorAll('.checklist input[type=checkbox]').forEach((cb, i) => {
    const id = cb.dataset.id || 'c' + i;
    cb.checked = !!saved[id];
    cb.closest('li').classList.toggle('checked', cb.checked);
    cb.addEventListener('change', () => {
      saved[id] = cb.checked;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
      cb.closest('li').classList.toggle('checked', cb.checked);
      updateCheckProgress();
    });
  });
  function updateCheckProgress() {
    const all = document.querySelectorAll('.checklist input[type=checkbox]');
    const done = [...all].filter((c) => c.checked).length;
    const el = document.getElementById('checkProgress');
    const bar = document.getElementById('checkBar');
    if (el) el.textContent = Math.round((done / all.length) * 100) + '%';
    if (bar) bar.style.width = (done / all.length) * 100 + '%';
  }
  updateCheckProgress();

  // Farm calculator
  const cyclesSlider = document.getElementById('cyclesPerDay');
  const cyclesVal = document.getElementById('cyclesVal');
  const hasTutorial = document.getElementById('hasTutorial');
  const calcGold = document.getElementById('calcGold');
  const calcBreakdown = document.getElementById('calcBreakdown');

  let GOLD_PER_WORK = 2404;
  let TUTORIAL_BONUS = 250000;
  let QUEST_BONUS = 75000;

  function updateCalc() {
    if (!cyclesSlider) return;
    const cycles = parseInt(cyclesSlider.value, 10);
    if (cyclesVal) cyclesVal.textContent = cycles;
    let day1 = cycles * GOLD_PER_WORK;
    if (hasTutorial && hasTutorial.checked) day1 += TUTORIAL_BONUS + QUEST_BONUS;
    const week = cycles * GOLD_PER_WORK * 7 + (hasTutorial && hasTutorial.checked ? TUTORIAL_BONUS + QUEST_BONUS : 0);
    const month = cycles * GOLD_PER_WORK * 30 + (hasTutorial && hasTutorial.checked ? TUTORIAL_BONUS + QUEST_BONUS : 0);
    if (calcGold) calcGold.textContent = day1.toLocaleString('tr-TR') + ' altın';
    if (calcBreakdown) {
      calcBreakdown.innerHTML =
        'Günlük work: ' + (cycles * GOLD_PER_WORK).toLocaleString('tr-TR') + ' altın (' + cycles + ' × ' + GOLD_PER_WORK + ')<br>' +
        (hasTutorial && hasTutorial.checked ? 'Tek seferlik: tutorial ~250k + quest ~75k<br>' : '') +
        '7 gün (work only): ' + (cycles * GOLD_PER_WORK * 7).toLocaleString('tr-TR') + '<br>' +
        '30 gün (work only): ' + (cycles * GOLD_PER_WORK * 30).toLocaleString('tr-TR');
    }
    updateChart(cycles);
  }
  if (cyclesSlider) {
    cyclesSlider.addEventListener('input', updateCalc);
    if (hasTutorial) hasTutorial.addEventListener('change', updateCalc);
    updateCalc();
  }

  // Chart.js projection
  let chartInstance = null;
  function updateChart(cyclesPerDay) {
    const canvas = document.getElementById('goldChart');
    if (!canvas || typeof Chart === 'undefined') return;
    const daily = cyclesPerDay * GOLD_PER_WORK;
    const labels = [];
    const data = [];
    let acc = (hasTutorial && hasTutorial.checked) ? TUTORIAL_BONUS + QUEST_BONUS : 0;
    for (let d = 0; d <= 14; d++) {
      labels.push('Gün ' + d);
      if (d > 0) acc += daily;
      data.push(acc);
    }
    if (chartInstance) chartInstance.destroy();
    chartInstance = new Chart(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Birikimli altın',
          data,
          borderColor: '#00e5a0',
          backgroundColor: 'rgba(0,229,160,0.1)',
          fill: true,
          tension: 0.3
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#8c9db5' } } },
        scales: {
          x: { ticks: { color: '#8c9db5' }, grid: { color: '#263242' } },
          y: { ticks: { color: '#8c9db5' }, grid: { color: '#263242' } }
        }
      }
    });
  }

  // Tabs
  document.querySelectorAll('.tabs').forEach((tabBar) => {
    const tabs = tabBar.querySelectorAll('.tab');
    const parent = tabBar.parentElement;
    tabs.forEach((tab) => {
      tab.addEventListener('click', () => {
        const target = tab.dataset.tab;
        tabs.forEach((t) => t.classList.remove('active'));
        tab.classList.add('active');
        parent.querySelectorAll('.tab-panel').forEach((p) => {
          p.classList.toggle('active', p.dataset.tab === target);
        });
      });
    });
  });

  function animateCounters() {
    document.querySelectorAll('[data-count]').forEach((el) => {
      const target = parseInt(el.dataset.count, 10);
      if (!target || isNaN(target)) return;
      let current = 0;
      const step = Math.max(1, Math.ceil(target / 40));
      const timer = setInterval(() => {
        current += step;
        if (current >= target) { current = target; clearInterval(timer); }
        el.textContent = current.toLocaleString('tr-TR');
      }, 30);
    });
  }

  function applyMeta(meta) {
    if (!meta) return;
    const w = meta.world || {};
    const e = meta.economy || {};
    const map = { players: w.total_players, endpoints: w.api_endpoints, countries: w.countries, factories: w.factories };
    document.querySelectorAll('[data-count]').forEach((el) => {
      const key = el.dataset.stat;
      if (key && map[key] != null) el.dataset.count = String(map[key]);
    });
    if (e.gold_per_work) GOLD_PER_WORK = e.gold_per_work;
    if (e.tutorial_bonus_gold) TUTORIAL_BONUS = e.tutorial_bonus_gold;
    if (e.quest_bonus_gold) QUEST_BONUS = e.quest_bonus_gold;
    const banner = document.getElementById('metaUpdated');
    if (banner && meta.updated_at) {
      banner.textContent = 'Veri güncelleme: ' + meta.updated_at + ' · v' + (meta.app_version || '?');
    }
    if (cyclesSlider) updateCalc();
    if (meta.checklist) renderQuestList(meta.checklist);
  }

  const sectionOrder = ['hero', 'architecture', 'core-loop', 'resources', 'classes', 'factories', 'day1', 'farm-loop', 'calculator', 'checklist', 'war', 'politics', 'social', 'api', 'endgame'];
  const nextFab = document.getElementById('nextFab');
  if (nextFab) {
    nextFab.addEventListener('click', () => {
      const ids = sectionOrder.filter((id) => document.getElementById(id));
      const y = window.scrollY + 80;
      let next = ids[0];
      for (let i = 0; i < ids.length; i++) {
        const el = document.getElementById(ids[i]);
        if (el && el.offsetTop > y) { next = ids[i]; break; }
        if (i === ids.length - 1) next = ids[ids.length - 1];
      }
      const target = document.getElementById(next);
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  fetch('/data/guide-meta.json')
    .then((r) => (r.ok ? r.json() : null))
    .then(applyMeta)
    .catch(() => {})
    .finally(animateCounters);

  // Pill cooldown visual
  const pillBtn = document.getElementById('pillSimBtn');
  const pillTimer = document.getElementById('pillTimer');
  const pillBar = document.getElementById('pillBar');
  if (pillBtn) {
    pillBtn.addEventListener('click', () => {
      pillBtn.disabled = true;
      const SIM_TOTAL = 60;
      let tick = SIM_TOTAL;
      if (pillTimer) pillTimer.textContent = '10:00 (sim)';
      const iv = setInterval(() => {
        tick--;
        const simSec = Math.round((tick / SIM_TOTAL) * 600);
        const m = Math.floor(simSec / 60);
        const s = simSec % 60;
        if (pillTimer) pillTimer.textContent = m + ':' + String(s).padStart(2, '0') + ' (sim)';
        if (pillBar) pillBar.style.width = ((SIM_TOTAL - tick) / SIM_TOTAL * 100) + '%';
        if (tick <= 0) {
          clearInterval(iv);
          pillBtn.disabled = false;
          if (pillTimer) pillTimer.textContent = 'Hazır';
          if (pillBar) pillBar.style.width = '0%';
        }
      }, 1000);
    });
  }
})();
