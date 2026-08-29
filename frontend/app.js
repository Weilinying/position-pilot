const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const elements = {
  portfolioForm: document.querySelector("#portfolio-form"),
  portfolioLoadButton: document.querySelector("#portfolio-form button"),
  userIdInput: document.querySelector("#user-id"),
  portfolioState: document.querySelector("#portfolio-state"),
  availableCash: document.querySelector("#available-cash"),
  positionCount: document.querySelector("#position-count"),
  positionsEmpty: document.querySelector("#positions-empty"),
  positionList: document.querySelector("#position-list"),
  portfolioMessage: document.querySelector("#portfolio-message"),
  questionForm: document.querySelector("#question-form"),
  question: document.querySelector("#question"),
  questionHint: document.querySelector("#question-hint"),
  askButton: document.querySelector("#ask-button"),
  resultTitle: document.querySelector("#result-title"),
  responseStatus: document.querySelector("#response-status"),
  answerCopy: document.querySelector("#answer-copy"),
  sourceCount: document.querySelector("#source-count"),
  sourceList: document.querySelector("#source-list"),
};

const clientState = {
  userIdInput: "",
  loadedUserId: null,
  portfolioGeneration: 0,
  questionGeneration: 0,
  portfolioController: null,
  questionController: null,
};

function normalizeUserId(value) {
  return value.trim().toLowerCase();
}

function isValidUserId(value) {
  return UUID_PATTERN.test(value);
}

function isPortfolioPayload(payload) {
  return (
    payload !== null &&
    typeof payload === "object" &&
    typeof payload.user_id === "string" &&
    typeof payload.available_cash === "string" &&
    payload.positions_are_complete === true &&
    Array.isArray(payload.positions) &&
    payload.positions.every(
      (position) =>
        position !== null &&
        typeof position === "object" &&
        typeof position.ticker === "string" &&
        typeof position.position_type === "string" &&
        typeof position.shares === "string" &&
        typeof position.average_cost === "string" &&
        typeof position.cost_basis === "string",
    )
  );
}

function isAnswerPayload(payload) {
  return (
    payload !== null &&
    typeof payload === "object" &&
    (payload.status === "OK" || payload.status === "DEGRADED") &&
    typeof payload.answer === "string" &&
    Array.isArray(payload.sources) &&
    payload.sources.every(
      (source) =>
        source !== null &&
        typeof source === "object" &&
        typeof source.type === "string" &&
        typeof source.status === "string",
    )
  );
}

function setPortfolioState(label, tone = "neutral") {
  elements.portfolioState.textContent = label;
  elements.portfolioState.dataset.tone = tone;
}

function setResponseState(label, tone = "neutral") {
  elements.responseStatus.textContent = label;
  elements.responseStatus.dataset.tone = tone;
}

function clearElement(element) {
  element.replaceChildren();
}

function setQuestionEnabled(enabled) {
  elements.question.disabled = !enabled;
  elements.askButton.disabled = !enabled;
  elements.questionHint.textContent = enabled
    ? "The loaded Portfolio User ID will be used for this request."
    : "Load a portfolio before asking.";
}

function resetResult(message = "Your answer will appear here with the exact context sources used.") {
  elements.resultTitle.textContent = "Awaiting a question";
  setResponseState("Idle");
  elements.answerCopy.textContent = message;
  elements.sourceCount.textContent = "0";
  clearElement(elements.sourceList);
  const placeholder = document.createElement("div");
  placeholder.className = "source-placeholder";
  placeholder.textContent = "No sources yet.";
  elements.sourceList.append(placeholder);
}

function resetPortfolio(message) {
  elements.availableCash.textContent = "—";
  elements.positionCount.textContent = "—";
  clearElement(elements.positionList);
  elements.positionsEmpty.hidden = false;
  elements.portfolioMessage.textContent = message ?? "";
}

function invalidateQuestionContext(resultMessage) {
  clientState.questionGeneration += 1;
  clientState.questionController?.abort();
  clientState.questionController = null;
  elements.askButton.textContent = "Ask PositionPilot ↗";
  setQuestionEnabled(false);
  resetResult(resultMessage);
}

function invalidateLoadedPortfolio(message) {
  clientState.portfolioGeneration += 1;
  clientState.portfolioController?.abort();
  clientState.portfolioController = null;
  clientState.loadedUserId = null;
  elements.portfolioLoadButton.disabled = false;
  elements.portfolioLoadButton.textContent = "Load";
  setPortfolioState("Stale", "warning");
  resetPortfolio(message);
  invalidateQuestionContext("Portfolio context changed. Reload it before asking a question.");
}

function handleUserIdInput() {
  clientState.userIdInput = normalizeUserId(elements.userIdInput.value);
  if (clientState.loadedUserId !== null) {
    if (clientState.userIdInput !== clientState.loadedUserId) {
      invalidateLoadedPortfolio("User ID changed. Load the new portfolio to continue.");
    }
    return;
  }
  if (clientState.portfolioController !== null) {
    invalidateLoadedPortfolio("User ID changed while loading. Load the intended portfolio again.");
    return;
  }
  setPortfolioState("Not loaded");
  resetPortfolio();
}

function createPositionCard(position) {
  const card = document.createElement("article");
  card.className = "position-card";

  const heading = document.createElement("div");
  heading.className = "position-card-heading";
  const ticker = document.createElement("strong");
  ticker.textContent = position.ticker;
  const positionType = document.createElement("span");
  positionType.className = "position-type";
  positionType.dataset.type = position.position_type === "SWING" ? "swing" : "long-term";
  positionType.textContent = position.position_type;
  heading.append(ticker, positionType);

  const facts = document.createElement("dl");
  facts.className = "position-facts";
  const factValues = [
    ["Shares", position.shares],
    ["Average cost", position.average_cost],
    ["Cost basis", position.cost_basis],
  ];
  for (const [label, value] of factValues) {
    const group = document.createElement("div");
    const term = document.createElement("dt");
    term.textContent = label;
    const description = document.createElement("dd");
    description.textContent = value;
    group.append(term, description);
    facts.append(group);
  }

  card.append(heading, facts);
  return card;
}

function renderPortfolio(portfolio) {
  elements.availableCash.textContent = `$${portfolio.available_cash}`;
  elements.positionCount.textContent = String(portfolio.positions.length);
  elements.portfolioMessage.textContent = "";
  clearElement(elements.positionList);
  elements.positionsEmpty.hidden = portfolio.positions.length > 0;

  if (portfolio.positions.length === 0) {
    const emptyMessage = elements.positionsEmpty.querySelector("p");
    emptyMessage.textContent = "This portfolio has no open positions.";
  } else {
    for (const position of portfolio.positions) {
      elements.positionList.append(createPositionCard(position));
    }
  }
  setPortfolioState("Loaded", "success");
  setQuestionEnabled(true);
}

async function parseApiError(response) {
  try {
    const payload = await response.json();
    if (payload?.detail?.message) {
      return {
        code: payload.detail.code ?? `HTTP_${response.status}`,
        message: payload.detail.message,
      };
    }
  } catch {
    // 非 JSON Failure 使用稳定的 HTTP 回退信息。
  }
  return {
    code: `HTTP_${response.status}`,
    message: "The request could not be completed.",
  };
}

async function loadPortfolio(event) {
  event.preventDefault();
  const requestedUserId = normalizeUserId(elements.userIdInput.value);
  clientState.userIdInput = requestedUserId;

  if (!isValidUserId(requestedUserId)) {
    invalidateLoadedPortfolio("Enter a valid Portfolio User ID.");
    setPortfolioState("Invalid ID", "danger");
    return;
  }

  clientState.portfolioGeneration += 1;
  const generation = clientState.portfolioGeneration;
  clientState.portfolioController?.abort();
  const controller = new AbortController();
  clientState.portfolioController = controller;
  clientState.loadedUserId = null;
  invalidateQuestionContext("Loading a portfolio. The previous decision context is no longer active.");

  setPortfolioState("Loading…");
  elements.portfolioLoadButton.disabled = true;
  elements.portfolioLoadButton.textContent = "Loading…";
  resetPortfolio("");

  try {
    const response = await fetch(`/v1/portfolios/${encodeURIComponent(requestedUserId)}`, {
      signal: controller.signal,
      headers: { Accept: "application/json" },
    });
    if (
      generation !== clientState.portfolioGeneration ||
      requestedUserId !== clientState.userIdInput
    ) {
      return;
    }
    if (!response.ok) {
      const error = await parseApiError(response);
      if (generation !== clientState.portfolioGeneration) {
        return;
      }
      setPortfolioState(error.code, "danger");
      resetPortfolio(error.message);
      return;
    }

    const portfolio = await response.json();
    if (
      generation !== clientState.portfolioGeneration ||
      requestedUserId !== clientState.userIdInput
    ) {
      return;
    }
    if (!isPortfolioPayload(portfolio)) {
      setPortfolioState("Invalid response", "danger");
      resetPortfolio("The portfolio response did not satisfy the expected contract.");
      return;
    }
    const responseUserId = normalizeUserId(portfolio.user_id ?? "");
    if (responseUserId !== requestedUserId) {
      setPortfolioState("Identity mismatch", "danger");
      resetPortfolio("The portfolio response belonged to a different User ID and was rejected.");
      return;
    }

    clientState.loadedUserId = responseUserId;
    renderPortfolio(portfolio);
    const url = new URL(window.location.href);
    url.searchParams.set("user_id", responseUserId);
    window.history.replaceState({}, "", url);
  } catch (error) {
    if (error.name === "AbortError" || generation !== clientState.portfolioGeneration) {
      return;
    }
    const isNetworkError = error instanceof TypeError;
    setPortfolioState(isNetworkError ? "Network error" : "Invalid response", "danger");
    resetPortfolio(
      isNetworkError
        ? "The portfolio service could not be reached."
        : "The portfolio response could not be safely displayed.",
    );
  } finally {
    if (generation === clientState.portfolioGeneration) {
      clientState.portfolioController = null;
      elements.portfolioLoadButton.disabled = false;
      elements.portfolioLoadButton.textContent = "Load";
    }
  }
}

function sourceTone(status) {
  if (status === "OK") {
    return "success";
  }
  if (status === "NO_DATA" || status === "NO_NEWS_FOUND") {
    return "warning";
  }
  return "danger";
}

function formatTimestamp(value) {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function createSourceCard(source) {
  const card = document.createElement("article");
  card.className = "source-card";
  card.dataset.tone = sourceTone(source.status);

  const top = document.createElement("div");
  top.className = "source-card-top";
  const title = document.createElement("strong");
  title.textContent = source.type;
  const status = document.createElement("span");
  status.className = "source-status";
  status.textContent = source.status;
  top.append(title, status);

  const metadata = document.createElement("div");
  metadata.className = "source-metadata";
  const fields = [
    source.ticker,
    source.provider,
    source.feed,
    formatTimestamp(source.market_timestamp),
    formatTimestamp(source.fetched_at),
  ].filter(Boolean);
  if (fields.length === 0) {
    fields.push("Structured portfolio state");
  }
  for (const value of fields) {
    const item = document.createElement("span");
    item.textContent = value;
    metadata.append(item);
  }

  card.append(top, metadata);
  return card;
}

function renderAnswer(payload) {
  const isDegraded = payload.status === "DEGRADED";
  elements.resultTitle.textContent = isDegraded ? "Answer with data gaps" : "Decision context assembled";
  setResponseState(payload.status, isDegraded ? "warning" : "success");
  elements.answerCopy.textContent = payload.answer;
  elements.sourceCount.textContent = String(payload.sources.length);
  clearElement(elements.sourceList);
  if (payload.sources.length === 0) {
    const placeholder = document.createElement("div");
    placeholder.className = "source-placeholder";
    placeholder.textContent = "This answer declared no external context sources.";
    elements.sourceList.append(placeholder);
    return;
  }
  for (const source of payload.sources) {
    elements.sourceList.append(createSourceCard(source));
  }
}

function renderQuestionError(error) {
  elements.resultTitle.textContent = "Request could not form an answer";
  setResponseState(error.code, "danger");
  elements.answerCopy.textContent = error.message;
  elements.sourceCount.textContent = "0";
  clearElement(elements.sourceList);
  const placeholder = document.createElement("div");
  placeholder.className = "source-placeholder";
  placeholder.textContent = "No answer or sources were accepted for this request.";
  elements.sourceList.append(placeholder);
}

async function askQuestion(event) {
  event.preventDefault();
  const question = elements.question.value.trim();
  const requestedUserId = clientState.loadedUserId;

  if (requestedUserId === null || requestedUserId !== clientState.userIdInput) {
    invalidateLoadedPortfolio("Portfolio context is stale. Load it again before asking.");
    return;
  }
  if (!question) {
    elements.questionHint.textContent = "Enter a question before submitting.";
    elements.question.focus();
    return;
  }

  clientState.questionGeneration += 1;
  const generation = clientState.questionGeneration;
  clientState.questionController?.abort();
  const controller = new AbortController();
  clientState.questionController = controller;

  elements.askButton.disabled = true;
  elements.askButton.textContent = "Analyzing…";
  elements.question.disabled = true;
  elements.resultTitle.textContent = "Assembling decision context";
  setResponseState("Working");
  elements.answerCopy.textContent = "Reading the loaded portfolio and selecting only the context this question needs.";
  elements.sourceCount.textContent = "0";
  clearElement(elements.sourceList);

  try {
    const response = await fetch("/v1/investment/questions", {
      method: "POST",
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ user_id: requestedUserId, question }),
    });
    if (
      generation !== clientState.questionGeneration ||
      requestedUserId !== clientState.loadedUserId ||
      requestedUserId !== clientState.userIdInput
    ) {
      return;
    }
    if (!response.ok) {
      const error = await parseApiError(response);
      if (
        generation !== clientState.questionGeneration ||
        requestedUserId !== clientState.loadedUserId ||
        requestedUserId !== clientState.userIdInput
      ) {
        return;
      }
      renderQuestionError(error);
      return;
    }
    const payload = await response.json();
    if (
      generation !== clientState.questionGeneration ||
      requestedUserId !== clientState.loadedUserId ||
      requestedUserId !== clientState.userIdInput
    ) {
      return;
    }
    if (!isAnswerPayload(payload)) {
      renderQuestionError({
        code: "INVALID_RESPONSE",
        message: "The investment response did not satisfy the expected contract.",
      });
      return;
    }
    renderAnswer(payload);
  } catch (error) {
    if (error.name === "AbortError" || generation !== clientState.questionGeneration) {
      return;
    }
    const isNetworkError = error instanceof TypeError;
    renderQuestionError({
      code: isNetworkError ? "NETWORK_ERROR" : "INVALID_RESPONSE",
      message: isNetworkError
        ? "The investment service could not be reached."
        : "The investment response could not be safely displayed.",
    });
  } finally {
    if (
      generation === clientState.questionGeneration &&
      requestedUserId === clientState.loadedUserId &&
      requestedUserId === clientState.userIdInput
    ) {
      clientState.questionController = null;
      elements.question.disabled = false;
      elements.askButton.disabled = false;
      elements.askButton.textContent = "Ask PositionPilot ↗";
      elements.questionHint.textContent = "The loaded Portfolio User ID will be used for this request.";
    }
  }
}

elements.userIdInput.addEventListener("input", handleUserIdInput);
elements.portfolioForm.addEventListener("submit", loadPortfolio);
elements.questionForm.addEventListener("submit", askQuestion);

const initialUserId = normalizeUserId(new URLSearchParams(window.location.search).get("user_id") ?? "");
if (initialUserId) {
  elements.userIdInput.value = initialUserId;
  clientState.userIdInput = initialUserId;
}
resetPortfolio();
resetResult();
