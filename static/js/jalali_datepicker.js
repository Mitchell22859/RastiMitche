(function () {
  "use strict";

  const G_D_M = [0,31,59,90,120,151,181,212,243,273,304,334];
  const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
  const MONTH_NAMES = ["فروردین","اردیبهشت","خرداد","تیر","مرداد","شهریور","مهر","آبان","آذر","دی","بهمن","اسفند"];

  function normalizeDigits(value) {
    return String(value || "")
      .replace(/[۰-۹]/g, d => String(PERSIAN_DIGITS.indexOf(d)))
      .replace(/[٠-٩]/g, d => String("٠١٢٣٤٥٦٧٨٩".indexOf(d)));
  }

  function pad(n) { return String(n).padStart(2, "0"); }

  function gregorianToJalali(gy, gm, gd) {
    let jy;
    if (gy > 1600) { jy = 979; gy -= 1600; }
    else { jy = 0; gy -= 621; }

    const gy2 = gm > 2 ? gy + 1 : gy;
    let days = 365 * gy + Math.floor((gy2 + 3) / 4) - Math.floor((gy2 + 99) / 100) +
      Math.floor((gy2 + 399) / 400) - 80 + gd + G_D_M[gm - 1];

    jy += 33 * Math.floor(days / 12053);
    days %= 12053;
    jy += 4 * Math.floor(days / 1461);
    days %= 1461;

    if (days > 365) {
      jy += Math.floor((days - 1) / 365);
      days = (days - 1) % 365;
    }

    let jm, jd;
    if (days < 186) {
      jm = 1 + Math.floor(days / 31);
      jd = 1 + (days % 31);
    } else {
      jm = 7 + Math.floor((days - 186) / 30);
      jd = 1 + ((days - 186) % 30);
    }
    return [jy, jm, jd];
  }

  function jalaliToGregorian(jy, jm, jd) {
    let gy;
    if (jy > 979) { gy = 1600; jy -= 979; }
    else { gy = 621; }

    let days = 365 * jy + Math.floor(jy / 33) * 8 + Math.floor(((jy % 33) + 3) / 4) + 78 + jd;
    if (jm < 7) days += (jm - 1) * 31;
    else days += ((jm - 7) * 30) + 186;

    gy += 400 * Math.floor(days / 146097);
    days %= 146097;

    if (days > 36524) {
      gy += 100 * Math.floor((days - 1) / 36524);
      days = (days - 1) % 36524;
      if (days >= 365) days++;
    }

    gy += 4 * Math.floor(days / 1461);
    days %= 1461;

    if (days > 365) {
      gy += Math.floor((days - 1) / 365);
      days = (days - 1) % 365;
    }

    let gd = days + 1;
    const leap = (gy % 4 === 0 && gy % 100 !== 0) || (gy % 400 === 0);
    const salA = [0,31,leap ? 29 : 28,31,30,31,30,31,31,30,31,30,31];

    let gm = 1;
    while (gm <= 12 && gd > salA[gm]) {
      gd -= salA[gm];
      gm++;
    }

    return [gy, gm, gd];
  }

  function todayJalali() {
    const d = new Date();
    return gregorianToJalali(d.getFullYear(), d.getMonth() + 1, d.getDate());
  }

  function parseJalali(value) {
    value = normalizeDigits(value).replace(/[-.]/g, "/").trim();
    const parts = value.split("/").filter(Boolean);
    if (parts.length !== 3) return null;
    const jy = parseInt(parts[0], 10);
    const jm = parseInt(parts[1], 10);
    const jd = parseInt(parts[2], 10);
    if (!jy || !jm || !jd) return null;
    if (jm < 1 || jm > 12 || jd < 1 || jd > 31) return null;
    return [jy, jm, jd];
  }

  function daysInJalaliMonth(jy, jm) {
    if (jm <= 6) return 31;
    if (jm <= 11) return 30;
    const g1 = jalaliToGregorian(jy, 1, 1)[0];
    const leap = ((jy + 38) * 682) % 2816 < 682;
    return leap ? 30 : 29;
  }

  let popup = null;
  let activeInput = null;
  let current = todayJalali();

  function ensurePopup() {
    if (popup) return popup;

    popup = document.createElement("div");
    popup.className = "rasti-jalali-datepicker";
    popup.dir = "rtl";
    document.body.appendChild(popup);

    document.addEventListener("click", function (e) {
      if (!popup || !activeInput) return;
      if (popup.contains(e.target) || e.target === activeInput) return;
      popup.classList.remove("is-open");
      activeInput = null;
    });

    return popup;
  }

  function render() {
    if (!popup || !activeInput) return;

    const [jy, jm] = current;
    const firstG = jalaliToGregorian(jy, jm, 1);
    const firstDate = new Date(firstG[0], firstG[1] - 1, firstG[2]);
    const startWeekday = (firstDate.getDay() + 1) % 7; // Saturday=0
    const dim = daysInJalaliMonth(jy, jm);

    let html = `
      <div class="jdp-header">
        <button type="button" data-jdp-prev>‹</button>
        <strong>${MONTH_NAMES[jm - 1]} ${jy}</strong>
        <button type="button" data-jdp-next>›</button>
      </div>
      <div class="jdp-weekdays">
        <span>ش</span><span>ی</span><span>د</span><span>س</span><span>چ</span><span>پ</span><span>ج</span>
      </div>
      <div class="jdp-days">
    `;

    for (let i = 0; i < startWeekday; i++) html += `<span></span>`;
    for (let d = 1; d <= dim; d++) {
      html += `<button type="button" data-jdp-day="${d}">${d}</button>`;
    }
    html += `</div>
      <div class="jdp-footer">
        <button type="button" data-jdp-clear>پاک کردن</button>
        <button type="button" data-jdp-today>امروز</button>
      </div>
    `;

    popup.innerHTML = html;

    popup.querySelector("[data-jdp-prev]").addEventListener("click", function () {
      current[1]--;
      if (current[1] < 1) { current[1] = 12; current[0]--; }
      render();
    });

    popup.querySelector("[data-jdp-next]").addEventListener("click", function () {
      current[1]++;
      if (current[1] > 12) { current[1] = 1; current[0]++; }
      render();
    });

    popup.querySelector("[data-jdp-clear]").addEventListener("click", function () {
      activeInput.value = "";
      popup.classList.remove("is-open");
      activeInput = null;
    });

    popup.querySelector("[data-jdp-today]").addEventListener("click", function () {
      const t = todayJalali();
      activeInput.value = `${t[0]}/${pad(t[1])}/${pad(t[2])}`;
      popup.classList.remove("is-open");
      activeInput = null;
    });

    popup.querySelectorAll("[data-jdp-day]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const day = parseInt(btn.dataset.jdpDay, 10);
        activeInput.value = `${current[0]}/${pad(current[1])}/${pad(day)}`;
        popup.classList.remove("is-open");
        activeInput = null;
      });
    });
  }

  function openFor(input) {
    activeInput = input;
    const parsed = parseJalali(input.value);
    current = parsed ? [parsed[0], parsed[1], parsed[2]] : todayJalali();

    const p = ensurePopup();
    render();

    const rect = input.getBoundingClientRect();
    p.style.top = `${window.scrollY + rect.bottom + 6}px`;
    p.style.left = `${window.scrollX + rect.left}px`;
    p.classList.add("is-open");
  }

  function attachDatepickers() {
    document.querySelectorAll("[data-jalali-datepicker]").forEach(function (input) {
      if (input.dataset.jdpAttached) return;
      input.dataset.jdpAttached = "1";
      input.setAttribute("autocomplete", "off");
      input.setAttribute("inputmode", "numeric");
      if (!input.placeholder) input.placeholder = "مثلاً 1404/12/01";

      input.addEventListener("focus", function () { openFor(input); });
      input.addEventListener("click", function () { openFor(input); });
    });
  }

  function convertRenderedDates() {
    document.querySelectorAll("[data-gregorian-date]").forEach(function (el) {
      if (el.dataset.jalaliConverted) return;
      const raw = el.getAttribute("data-gregorian-date") || el.textContent;
      const m = String(raw || "").match(/(\d{4})-(\d{2})-(\d{2})(?:[T\s](\d{2}):(\d{2}))?/);
      if (!m) return;
      const j = gregorianToJalali(parseInt(m[1],10), parseInt(m[2],10), parseInt(m[3],10));
      let text = `${j[0]}/${pad(j[1])}/${pad(j[2])}`;
      if (m[4]) text += ` ${m[4]}:${m[5]}`;
      el.textContent = text;
      el.dataset.jalaliConverted = "1";
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    attachDatepickers();
    convertRenderedDates();
  });

  window.RastiJalaliDatepicker = {
    attach: attachDatepickers,
    gregorianToJalali,
    jalaliToGregorian,
    parseJalali
  };
})();
