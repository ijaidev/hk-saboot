(() => {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));

  const els = {
    uploadView: $("#upload-view"),
    processingView: $("#processing-view"),
    reportView: $("#report-view"),
    appealView: $("#appeal-view"),
    fileInput: $("#file-input"),
    dropzone: $("#dropzone"),
    fileMeta: $("#file-meta"),
    auditButton: $("#audit-button"),
    demoButton: $("#demo-button"),
    uploadError: $("#upload-error"),
    processingTitle: $("#processing-title"),
    statementTitle: $("#statement-title"),
    statementMeta: $("#statement-meta"),
    riskPanel: $("#risk-panel"),
    riskGauge: $("#risk-gauge"),
    riskScore: $("#risk-score"),
    riskLabel: $("#risk-label"),
    riskDescription: $("#risk-description"),
    riskFactors: $("#risk-factors"),
    summaryDisputed: $("#summary-disputed"),
    summaryClaims: $("#summary-claims"),
    summaryVerifier: $("#summary-verifier"),
    summaryReview: $("#summary-review"),
    claimsList: $("#claims-list"),
    reviewSection: $("#review-section"),
    reviewList: $("#review-list"),
    reviewCheck: $("#review-check"),
    approveButton: $("#approve-button"),
    appealButton: $("#appeal-button"),
    approvalStatus: $("#approval-status"),
    appealMeta: $("#appeal-meta"),
    appealVerifier: $("#appeal-verifier"),
    appealSubject: $("#appeal-subject"),
    appealBody: $("#appeal-body"),
    appealCitations: $("#appeal-citations"),
    downloadButton: $("#download-button"),
    restartButton: $("#restart-button"),
    toast: $("#toast"),
  };

  const state = {
    auditId: null,
    audit: null,
    selected: new Set(),
    approved: new Set(),
    appeal: null,
    file: null,
    processingTimer: null,
    toastTimer: null,
  };

  const money = (value) =>
    "₹" +
    Number(value || 0).toLocaleString("en-IN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

  const escapeHtml = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (character) => {
      const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
      return map[character];
    });

  const escapeAttr = (value) => escapeHtml(value).replace(/"/g, "&quot;");

  const titleCase = (value) =>
    String(value || "")
      .replaceAll("_", " ")
      .replace(/^\w/, (character) => character.toUpperCase());

  const formatWhen = (iso) => {
    if (!iso) return "";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return iso;
    return date.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
  };

  function showView(name) {
    els.uploadView.hidden = name !== "upload";
    els.processingView.hidden = name !== "processing";
    els.reportView.hidden = name !== "report";
    els.appealView.hidden = name !== "appeal";
  }

  function showToast(message, isError = false) {
    els.toast.textContent = message;
    els.toast.classList.toggle("is-error", isError);
    els.toast.hidden = false;
    window.clearTimeout(state.toastTimer);
    state.toastTimer = window.setTimeout(() => {
      els.toast.hidden = true;
    }, 4200);
  }

  function showUploadError(message) {
    els.uploadError.textContent = message;
    els.uploadError.hidden = !message;
  }

  async function api(path, options = {}) {
    const response = await fetch(path, options);
    let data = null;
    try {
      data = await response.json();
    } catch (error) {
      data = null;
    }
    if (!response.ok) {
      throw new Error((data && data.error) || `Request failed (${response.status})`);
    }
    return data;
  }

  function resetState() {
    window.clearInterval(state.processingTimer);
    state.auditId = null;
    state.audit = null;
    state.selected = new Set();
    state.approved = new Set();
    state.appeal = null;
    state.file = null;
    els.fileInput.value = "";
    els.fileMeta.textContent = "No file selected.";
    els.auditButton.disabled = true;
    els.reviewCheck.checked = false;
    els.reviewCheck.disabled = false;
    els.approveButton.disabled = true;
    els.appealButton.disabled = true;
    els.approvalStatus.textContent = "";
    els.uploadError.hidden = true;
    els.toast.hidden = true;
    showView("upload");
    window.scrollTo({ top: 0, behavior: "auto" });
  }

  function handleFile(file) {
    if (!file) return;
    const name = file.name || "statement";
    const lower = name.toLowerCase();
    if (!lower.endsWith(".pdf") && !lower.endsWith(".zip")) {
      showUploadError("Choose a text PDF or a CSV bundle .zip.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      showUploadError("That file is larger than 10 MB.");
      return;
    }
    state.file = file;
    showUploadError("");
    els.fileMeta.innerHTML = `Selected: <strong>${escapeHtml(name)}</strong> · ${(file.size / 1024).toFixed(1)} KB`;
    els.auditButton.disabled = false;
    console.info(`[saboot] file-selected ${name} ${file.size}`);
  }

  function readFileAsDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(new Error("Could not read the file."));
      reader.readAsDataURL(file);
    });
  }

  function startProcessing(title) {
    showView("processing");
    els.processingTitle.textContent = title;
    const steps = $$(".processing-steps li");
    steps.forEach((step) => step.classList.remove("is-active"));
    let index = 0;
    steps[0]?.classList.add("is-active");
    window.clearInterval(state.processingTimer);
    state.processingTimer = window.setInterval(() => {
      index = Math.min(index + 1, steps.length - 1);
      steps.forEach((step, stepIndex) => step.classList.toggle("is-active", stepIndex === index));
    }, 380);
  }

  function stopProcessing() {
    window.clearInterval(state.processingTimer);
    state.processingTimer = null;
  }

  async function runAudit() {
    if (!state.file) return;
    showUploadError("");
    startProcessing("Reading the statement…");
    try {
      const dataUrl = await readFileAsDataUrl(state.file);
      const base64 = dataUrl.split(",", 2)[1] || "";
      const kind = state.file.name.toLowerCase().endsWith(".pdf") ? "pdf" : "zip";
      const data = await api("/api/audit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filename: state.file.name,
          kind,
          data: base64,
        }),
      });
      stopProcessing();
      state.auditId = data.audit_id;
      state.audit = data.audit;
      renderReport(data.audit, { scroll: true });
      console.info(`[saboot] audit-complete ${data.audit.summary.claim_count} claims`);
    } catch (error) {
      stopProcessing();
      showView("upload");
      showUploadError(error.message || "Audit failed.");
      showToast(error.message || "Audit failed.", true);
      console.info(`[saboot] audit-error ${error.message}`);
    }
  }

  async function loadDemo() {
    startProcessing("Loading the sample case…");
    try {
      const data = await api("/api/demo");
      stopProcessing();
      state.auditId = data.audit_id;
      state.audit = data.audit;
      renderReport(data.audit, { scroll: true });
      console.info("[saboot] demo-loaded");
    } catch (error) {
      stopProcessing();
      showView("upload");
      showUploadError(error.message || "Could not load the sample case.");
      showToast(error.message || "Could not load the sample case.", true);
    }
  }

  function claimById(claimId) {
    return (state.audit?.claims || []).find((claim) => claim.claim_id === claimId);
  }

  function selectedReadyClaims() {
    return Array.from(state.selected)
      .map(claimById)
      .filter((claim) => claim && claim.status === "ready");
  }

  function updateApprovalControls() {
    const approved = state.approved.size > 0;
    const ready = selectedReadyClaims();
    els.approveButton.disabled = approved || !els.reviewCheck.checked || ready.length === 0;
    els.appealButton.disabled = !approved;
    els.reviewCheck.disabled = approved;
    els.reviewCheck.closest(".check-row")?.classList.toggle("is-approved", approved);
    if (approved) {
      const when = formatWhen(state.audit?.approval?.approved_at);
      els.approvalStatus.textContent = `Approved ${state.approved.size} claim${state.approved.size === 1 ? "" : "s"}${when ? ` · ${when}` : ""}. Ready to draft.`;
    } else if (els.reviewCheck.checked && ready.length > 0) {
      els.approvalStatus.textContent = `${ready.length} claim${ready.length === 1 ? "" : "s"} selected for approval.`;
    } else if (els.reviewCheck.checked) {
      els.approvalStatus.textContent = "Select at least one ready claim.";
    } else {
      els.approvalStatus.textContent = "";
    }
  }

  function renderReport(audit, { scroll = false } = {}) {
    state.audit = audit;
    state.auditId = audit.audit_id || state.auditId;
    state.approved = new Set(audit.approval?.approved_claim_ids || []);
    state.selected = new Set(
      (audit.claims || [])
        .filter((claim) => claim.status === "ready")
        .map((claim) => claim.claim_id)
    );
    els.reviewCheck.checked = false;
    els.reviewCheck.disabled = state.approved.size > 0;

    const meta = audit.statement.meta;
    els.statementTitle.textContent = meta.statement_id;
    els.statementMeta.textContent = `${meta.platform} · Worker ${meta.worker_id} · ${meta.period_start.slice(0, 10)} to ${meta.period_end.slice(0, 10)} · ${meta.jurisdiction}`;

    const risk = audit.risk || { score: 0, band: "low", label: "Review priority", description: "", factors: {} };
    els.riskPanel.className = `risk-panel risk-${risk.band}`;
    els.riskGauge.style.setProperty("--score", String(risk.score || 0));
    els.riskScore.textContent = String(risk.score || 0);
    els.riskLabel.textContent = risk.label || "Review priority";
    els.riskDescription.textContent = risk.description || "Estimates how much of this statement needs review.";
    const factors = risk.factors || {};
    els.riskFactors.textContent = `${money(factors.disputed_amount)} of ${money(factors.statement_pay)} statement pay · ${factors.claim_count || 0} claims · ${factors.needs_review_count || 0} review items`;

    els.summaryDisputed.textContent = money(audit.summary.total_potential);
    els.summaryClaims.textContent = String(audit.summary.claim_count);
    els.summaryVerifier.textContent = audit.summary.verification_passed ? "PASS" : "FAIL";
    els.summaryReview.textContent = String(
      (audit.summary.review_item_count || 0) + (audit.summary.needs_review_count || 0)
    );

    renderClaims(audit);
    renderReviewItems(audit.review_items || []);
    updateApprovalControls();
    showView("report");
    if (scroll) window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function policyHtml(claim) {
    const clause = claim.policy_clause;
    if (!clause) {
      return `<div class="policy-line" data-testid="policy-citation"><span class="policy-key">Policy</span><span>No applicable clause found · needs human review</span></div>`;
    }
    return `
      <div class="policy-line" data-testid="policy-citation">
        <span class="policy-key">Policy</span>
        <a href="${escapeAttr(clause.source_url)}" target="_blank" rel="noreferrer">${escapeHtml(clause.id)} — ${escapeHtml(clause.title)}</a>
        <span class="policy-date">Effective ${escapeHtml(clause.effective_from)} → ${escapeHtml(clause.effective_to)} · ${escapeHtml(String(clause.source_url || "").replace(/^https?:\/\//, ""))}</span>
      </div>
    `;
  }

  function sourceRowsText(sourceRows) {
    if (!sourceRows) return "—";
    const parts = [];
    Object.entries(sourceRows).forEach(([kind, mapping]) => {
      if (mapping && typeof mapping === "object") {
        Object.entries(mapping).forEach(([identifier, source]) => {
          parts.push(`${kind}:${identifier} → ${source}`);
        });
      }
    });
    return parts.join("; ") || "—";
  }

  function claimCard(claim) {
    const checked = state.selected.has(claim.claim_id);
    const approved = state.approved.has(claim.claim_id);
    const isReady = claim.status === "ready";
    const quote = claim.evidence?.quote || claim.evidence?.arithmetic || "No source quote available.";
    const refs = [
      ...(claim.order_ids || []).map((id) => `order ${id}`),
      ...(claim.deduction_ids || []).map((id) => `deduction ${id}`),
      ...(claim.incentive_ids || []).map((id) => `incentive ${id}`),
    ].join(" · ");
    const verifierPassed = Boolean(claim.verification?.passed);
    const verifierErrors = claim.verification?.errors || [];
    return `
      <article class="claim-card ${approved ? "is-approved" : ""} ${checked ? "" : "is-unselected"}"
        data-testid="claim-card" data-claim-id="${escapeAttr(claim.claim_id)}" data-status="${escapeAttr(claim.status)}">
        <div class="claim-top">
          <label class="claim-select">
            <input class="claim-checkbox" type="checkbox" data-claim-id="${escapeAttr(claim.claim_id)}"
              ${checked ? "checked" : ""} ${isReady && !approved ? "" : "disabled"}
              aria-label="Include ${escapeAttr(titleCase(claim.claim_type))} in the appeal">
          </label>
          <div class="claim-titles">
            <span class="claim-type">${escapeHtml(titleCase(claim.claim_type))}</span>
            <span class="claim-refs">${escapeHtml(refs || "no references")}</span>
          </div>
          <div class="claim-amount">${escapeHtml(claim.amount_display || money(claim.amount))}</div>
        </div>
        <div class="claim-badges">
          <span class="chip ${isReady ? "chip-ready" : "chip-review"}">${isReady ? "Ready for review" : "Needs review"}</span>
          <span class="chip chip-confidence">Confidence ${Number(claim.confidence || 0).toFixed(2)}</span>
          ${approved ? '<span class="chip chip-approved">Approved</span>' : ""}
        </div>
        <blockquote class="claim-quote" data-testid="evidence-quote">${escapeHtml(quote)}</blockquote>
        <p class="claim-why">${escapeHtml(claim.reason || "")}</p>
        ${policyHtml(claim)}
        <details class="evidence-details" data-testid="evidence-details">
          <summary data-testid="evidence-toggle">View evidence</summary>
          <div class="evidence-grid">
            <div><span>Arithmetic</span><p>${escapeHtml(claim.evidence?.arithmetic || "—")}</p></div>
            <div><span>Source rows</span><p>${escapeHtml(sourceRowsText(claim.evidence?.source_rows))}</p></div>
            <div><span>Order / deduction IDs</span><p>${escapeHtml(refs || "—")}</p></div>
            <div><span>Verifier</span><p>${verifierPassed ? "PASS" : "FAIL"}: ${escapeHtml(verifierErrors.join("; ") || "all checks passed")}</p></div>
          </div>
        </details>
      </article>
    `;
  }

  function renderClaims(audit) {
    const claims = audit.claims || [];
    if (!claims.length) {
      els.claimsList.innerHTML = `
        <div class="empty-state">
          <strong>No claims detected.</strong>
          <p>The statement reconciles cleanly against the policy pack. Nothing to approve.</p>
        </div>
      `;
      return;
    }
    els.claimsList.innerHTML = claims.map(claimCard).join("");
    $$(".claim-checkbox").forEach((checkbox) => {
      checkbox.addEventListener("change", () => {
        const claimId = checkbox.dataset.claimId;
        if (!claimId) return;
        if (checkbox.checked) state.selected.add(claimId);
        else state.selected.delete(claimId);
        const card = checkbox.closest(".claim-card");
        card?.classList.toggle("is-unselected", !checkbox.checked);
        updateApprovalControls();
        console.info(`[saboot] claim-toggle ${claimId} ${checkbox.checked}`);
      });
    });
  }

  function renderReviewItems(items) {
    if (!items.length) {
      els.reviewSection.hidden = true;
      els.reviewList.innerHTML = "";
      return;
    }
    els.reviewSection.hidden = false;
    els.reviewList.innerHTML = items
      .map(
        (item) => `
        <div class="review-card" data-testid="review-item">
          <strong>${escapeHtml(titleCase(item.review_type))}</strong>
          <p>${escapeHtml(item.description || "")}</p>
          <div class="review-refs">${escapeHtml(
            [
              ...(item.order_ids || []).map((id) => `order ${id}`),
              ...(item.deduction_ids || []).map((id) => `deduction ${id}`),
              ...(item.incentive_ids || []).map((id) => `incentive ${id}`),
            ].join(" · ") || "no references"
          )}</div>
        </div>
      `
      )
      .join("");
  }

  async function approveSelected() {
    if (!state.auditId) return;
    const claimIds = selectedReadyClaims().map((claim) => claim.claim_id);
    if (!claimIds.length) return;
    els.approveButton.disabled = true;
    try {
      const data = await api("/api/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ audit_id: state.auditId, claim_ids: claimIds }),
      });
      state.audit = data.audit;
      state.approved = new Set(data.audit.approval?.approved_claim_ids || []);
      renderReport(data.audit, { scroll: false });
      showToast(`Approved ${claimIds.length} claim${claimIds.length === 1 ? "" : "s"}. Nothing has been sent.`);
      console.info(`[saboot] claims-approved ${claimIds.join(",")}`);
    } catch (error) {
      showToast(error.message || "Approval failed.", true);
      els.approveButton.disabled = false;
      console.info(`[saboot] approval-error ${error.message}`);
    }
  }

  async function generateAppeal() {
    if (!state.auditId) return;
    els.appealButton.disabled = true;
    try {
      const data = await api("/api/appeal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ audit_id: state.auditId }),
      });
      state.appeal = data.appeal;
      renderAppeal(data.appeal);
      console.info(`[saboot] appeal-generated verifier=${data.appeal.verification.passed}`);
    } catch (error) {
      showToast(error.message || "Appeal generation failed.", true);
      els.appealButton.disabled = false;
      console.info(`[saboot] appeal-error ${error.message}`);
    }
  }

  function renderAppeal(appeal) {
    const provider =
      appeal.provider === "template"
        ? "Template draft · no API key"
        : `LLM draft · ${appeal.provider}`;
    els.appealMeta.textContent = `${appeal.total_display} · ${provider} · ${appeal.claim_ids.length} claim${appeal.claim_ids.length === 1 ? "" : "s"}`;
    els.appealVerifier.textContent = `Verifier ${appeal.verification?.passed ? "PASS" : "FAIL"}`;
    els.appealVerifier.classList.toggle("is-fail", !appeal.verification?.passed);
    els.appealSubject.textContent = `Subject: ${appeal.subject}`;
    els.appealBody.textContent = appeal.body;
    els.appealCitations.innerHTML = (appeal.citations || [])
      .map(
        (citation) => `
        <li>
          <strong>${escapeHtml(citation.id)} — ${escapeHtml(citation.title)}</strong>
          <a href="${escapeAttr(citation.source_url)}" target="_blank" rel="noreferrer">${escapeHtml(citation.source_url)}</a>
        </li>
      `
      )
      .join("") || "<li>No citations.</li>";
    showView("appeal");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function downloadPdf() {
    if (!state.auditId) return;
    els.downloadButton.disabled = true;
    try {
      const response = await fetch("/api/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ audit_id: state.auditId }),
      });
      if (!response.ok) {
        let message = `Export failed (${response.status})`;
        try {
          const body = await response.json();
          message = body.error || message;
        } catch (error) {
          // ignore
        }
        throw new Error(message);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `saboot-appeal-${state.auditId.slice(0, 8)}.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1500);
      showToast("PDF export prepared. Nothing has been sent.");
      console.info("[saboot] pdf-exported");
    } catch (error) {
      showToast(error.message || "PDF export failed.", true);
      console.info(`[saboot] export-error ${error.message}`);
    } finally {
      els.downloadButton.disabled = false;
    }
  }

  els.fileInput.addEventListener("change", (event) => handleFile(event.target.files?.[0]));

  ["dragenter", "dragover"].forEach((eventName) => {
    els.dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      els.dropzone.classList.add("is-dragging");
    });
  });
  ["dragleave", "drop"].forEach((eventName) => {
    els.dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      els.dropzone.classList.remove("is-dragging");
    });
  });
  els.dropzone.addEventListener("drop", (event) => {
    handleFile(event.dataTransfer?.files?.[0]);
  });
  els.dropzone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      els.fileInput.click();
    }
  });

  els.auditButton.addEventListener("click", runAudit);
  els.demoButton.addEventListener("click", loadDemo);
  els.reviewCheck.addEventListener("change", updateApprovalControls);
  els.approveButton.addEventListener("click", approveSelected);
  els.appealButton.addEventListener("click", generateAppeal);
  els.downloadButton.addEventListener("click", downloadPdf);
  els.restartButton.addEventListener("click", resetState);

  updateApprovalControls();
  console.info("[saboot] ui-ready");
})();
