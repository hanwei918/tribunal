"use strict";
// A minimal DOM, enough for the viewer's own script and nothing more.
//
// Why this exists: the defects it catches are invisible to every test that reads
// the page as text. ``ui/build.py --check`` compares bytes, the byte-equality
// test compares bytes, and a source-text test looks for a phrase -- none of them
// can see that ``renderOverview`` throws on load because a string was handed to
// ``appendChild``. The only way to see it is to run the script, so this shim
// runs it.
//
// It is deliberately small and deliberately strict. ``appendChild`` throws when
// its argument is not a node, exactly as a browser does, because that is the
// defect this harness was written for; a shim that quietly accepted a string
// would have passed the very page it is meant to fail.
//
// No npm package and no network. Run it as:
//
//     node tests/support/dom_shim.js <job.json>
//
// The job names pages and the views to render on each; the output is JSON on
// stdout. See ``tests/test_ui_build.py`` for the caller.

const fs = require("fs");
const vm = require("vm");

// --------------------------------------------------------------------------
// The node tree
// --------------------------------------------------------------------------
// Everything tree-shaped and event-shaped lives here, so ``Document`` -- which
// is a node too -- has ``appendChild`` and ``dispatchEvent`` without restating
// them. Attributes and classes are the ``Element``'s own.
class Node {
  constructor() {
    this.childNodes = [];
    this.parentNode = null;
    this.listeners = new Map();
  }

  get firstChild() {
    return this.childNodes.length ? this.childNodes[0] : null;
  }

  appendChild(child) {
    if (!(child instanceof Node)) {
      throw new TypeError(
        "Failed to execute 'appendChild' on 'Node': parameter 1 is not of " +
          "type 'Node'."
      );
    }
    if (child.parentNode) {
      child.parentNode.removeChild(child);
    }
    this.childNodes.push(child);
    child.parentNode = this;
    return child;
  }

  removeChild(child) {
    const at = this.childNodes.indexOf(child);
    if (at < 0) {
      throw new Error("removeChild: the node is not a child of this node");
    }
    this.childNodes.splice(at, 1);
    child.parentNode = null;
    return child;
  }

  contains(other) {
    for (let node = other; node; node = node.parentNode) {
      if (node === this) {
        return true;
      }
    }
    return false;
  }

  get textContent() {
    let out = "";
    for (const child of this.childNodes) {
      out += child.textContent;
    }
    return out;
  }
  set textContent(value) {
    this.childNodes = [];
    this.appendChild(new TextNode(value));
  }

  addEventListener(type, handler) {
    const key = String(type);
    if (!this.listeners.has(key)) {
      this.listeners.set(key, []);
    }
    this.listeners.get(key).push(handler);
  }

  dispatchEvent(event) {
    const key = String(event.type);
    event.target = event.target || this;
    for (const handler of (this.listeners.get(key) || []).slice()) {
      event.currentTarget = this;
      handler.call(this, event);
    }
    return true;
  }

  focus() {
    if (this.ownerDocument) {
      this.ownerDocument.activeElement = this;
    }
  }

  scrollIntoView() {}

  descendants() {
    const out = [];
    const walk = (node) => {
      for (const child of node.childNodes) {
        if (child instanceof Element) {
          out.push(child);
          walk(child);
        }
      }
    };
    walk(this);
    return out;
  }

  // Only the two selector shapes the page uses: ``[attr]`` and
  // ``[attr="value"]``. A selector this does not understand throws rather than
  // answering with nothing, so a new selector shape shows up as a failure and
  // not as a page that quietly renders less.
  querySelectorAll(selector) {
    const match = /^\[([^\]=\s]+)(?:=(?:"([^"]*)"|'([^']*)'))?\]$/.exec(
      String(selector).trim()
    );
    if (!match) {
      throw new Error("the shim cannot answer the selector " + selector);
    }
    const name = match[1];
    const wanted = match[2] !== undefined ? match[2] : match[3];
    return this.descendants().filter((node) => {
      const value = node.getAttribute(name);
      if (value === null) {
        return false;
      }
      return wanted === undefined ? true : value === wanted;
    });
  }
}

class TextNode extends Node {
  constructor(value) {
    super();
    this.nodeValue = String(value);
  }
  get textContent() {
    return this.nodeValue;
  }
  set textContent(value) {
    this.nodeValue = String(value);
  }
}

class Element extends Node {
  constructor(tagName) {
    super();
    this.tagName = String(tagName).toUpperCase();
    this.attributes = new Map();
    this.classes = new Set();
    this.hidden = false;
    this.disabled = false;
    this.checked = false;
    this.value = "";
  }

  setAttribute(name, value) {
    const key = String(name);
    this.attributes.set(key, String(value));
    if (key === "class") {
      this.classes = new Set(String(value).split(/\s+/).filter(Boolean));
    }
  }

  getAttribute(name) {
    const key = String(name);
    return this.attributes.has(key) ? this.attributes.get(key) : null;
  }

  removeAttribute(name) {
    this.attributes.delete(String(name));
  }

  get id() {
    const value = this.attributes.get("id");
    return value === undefined ? "" : value;
  }

  get className() {
    return Array.from(this.classes).join(" ");
  }
  set className(value) {
    this.classes = new Set(String(value).split(/\s+/).filter(Boolean));
  }

  get classList() {
    const classes = this.classes;
    return {
      add: (name) => classes.add(String(name)),
      remove: (name) => classes.delete(String(name)),
      contains: (name) => classes.has(String(name)),
      toggle: (name, force) => {
        const key = String(name);
        const on = force === undefined ? !classes.has(key) : !!force;
        if (on) {
          classes.add(key);
        } else {
          classes.delete(key);
        }
        return on;
      },
    };
  }
}

class Document extends Node {
  constructor() {
    super();
    this.documentElement = new Element("html");
    this.body = new Element("body");
    this.documentElement.appendChild(this.body);
    this.appendChild(this.documentElement);
    this.activeElement = this.body;
    this.ownerDocument = this;
  }

  createElement(tagName) {
    const node = new Element(tagName);
    node.ownerDocument = this;
    return node;
  }

  createTextNode(value) {
    const node = new TextNode(value);
    node.ownerDocument = this;
    return node;
  }

  getElementById(id) {
    const wanted = String(id);
    if (this.body.id === wanted) {
      return this.body;
    }
    return this.descendants().find((node) => node.id === wanted) || null;
  }
}

class Window {
  constructor() {
    this.location = { hash: "" };
    this.listeners = new Map();
    this.scrolled = 0;
  }
  addEventListener(type, handler) {
    const key = String(type);
    if (!this.listeners.has(key)) {
      this.listeners.set(key, []);
    }
    this.listeners.get(key).push(handler);
  }
  dispatchEvent(event) {
    const key = String(event.type);
    event.target = event.target || this;
    for (const handler of (this.listeners.get(key) || []).slice()) {
      event.currentTarget = this;
      handler.call(this, event);
    }
    return true;
  }
  scrollTo() {
    this.scrolled += 1;
  }
}

// --------------------------------------------------------------------------
// Enough of an HTML parser for the page this repository writes
// --------------------------------------------------------------------------
const VOID_ELEMENTS = new Set([
  "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
  "param", "source", "track", "wbr",
]);

const TAG = /<(\/?)([a-zA-Z][a-zA-Z0-9-]*)((?:"[^"]*"|'[^']*'|[^>"'])*?)(\/?)>/g;
const ATTRIBUTE = /([a-zA-Z_:][-a-zA-Z0-9_:.]*)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'))?/g;

function decodeEntities(text) {
  return text
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, "&");
}

function attributeValue(match) {
  if (match[2] !== undefined) {
    return decodeEntities(match[2]);
  }
  if (match[3] !== undefined) {
    return decodeEntities(match[3]);
  }
  return "";
}

function parseInto(document, parent, markup) {
  const stack = [parent];
  let at = 0;
  TAG.lastIndex = 0;
  let match;
  while ((match = TAG.exec(markup)) !== null) {
    const between = markup.slice(at, match.index);
    if (between.trim()) {
      stack[stack.length - 1].appendChild(
        document.createTextNode(decodeEntities(between))
      );
    }
    at = TAG.lastIndex;

    if (match[1] === "/") {
      for (let i = stack.length - 1; i > 0; i -= 1) {
        if (stack[i].tagName === match[2].toUpperCase()) {
          stack.length = i;
          break;
        }
      }
      continue;
    }

    const node = document.createElement(match[2]);
    ATTRIBUTE.lastIndex = 0;
    let attribute;
    while ((attribute = ATTRIBUTE.exec(match[3])) !== null) {
      node.setAttribute(attribute[1], attributeValue(attribute));
    }
    stack[stack.length - 1].appendChild(node);
    if (!VOID_ELEMENTS.has(match[2].toLowerCase()) && match[4] !== "/") {
      stack.push(node);
    }
  }
  const rest = markup.slice(at);
  if (rest.trim()) {
    stack[stack.length - 1].appendChild(
      document.createTextNode(decodeEntities(rest))
    );
  }
}

// --------------------------------------------------------------------------
// Splitting one page into its three parts
// --------------------------------------------------------------------------
const DATA_MARKER = '<script id="tribunal-data"';

function splitPage(html) {
  const dataAt = html.indexOf(DATA_MARKER);
  if (dataAt < 0) {
    return { body: null, data: null, script: null };
  }
  const bodyAt = html.indexOf("<body>");
  const body = html.slice(bodyAt + "<body>".length, dataAt);
  const dataOpen = html.indexOf(">", dataAt) + 1;
  const data = html.slice(dataOpen, html.indexOf("</script>", dataOpen));
  const scriptAt = html.lastIndexOf("<script>");
  if (scriptAt < 0) {
    return { body, data, script: null };
  }
  const script = html.slice(
    scriptAt + "<script>".length,
    html.indexOf("</script>", scriptAt)
  );
  return { body, data, script };
}

function describe(error) {
  if (error && error.name && error.message) {
    return error.name + ": " + error.message;
  }
  return String(error);
}

function hashFor(target) {
  if (target.view === "case") {
    return "#view=case&case=" + target.case + "&step=" + target.step;
  }
  if (target.view === "stance") {
    return "#view=stance&case=" + target.case;
  }
  return "#view=overview";
}

// --------------------------------------------------------------------------
// Running one page
// --------------------------------------------------------------------------
function runPage(job) {
  const html = fs.readFileSync(job.path, "utf8");
  const { body, data, script } = splitPage(html);
  const result = {
    name: job.name,
    has_script: Boolean(script),
    load_error: null,
    overview_children: 0,
    rendered: 0,
    exceptions: [],
  };
  if (!script) {
    return result;
  }

  const document = new Document();
  const window = new Window();
  parseInto(document, document.body, body);

  // The data block the page carries, read the way the page itself reads it.
  const dataElement = document.createElement("script");
  dataElement.setAttribute("id", "tribunal-data");
  dataElement.textContent = data;
  document.body.appendChild(dataElement);

  const sandbox = { document, window, Node, console };
  vm.createContext(sandbox);
  try {
    vm.runInContext(script, sandbox, { filename: job.name + ".js" });
  } catch (error) {
    result.load_error = describe(error);
  }

  // The overview is what the page renders on load, so its own render is
  // measured here rather than driven: a load that threw part-way leaves this
  // short, and ``load_error`` says why.
  const overview = document.getElementById("view-overview");
  result.overview_children = overview ? overview.childNodes.length : 0;

  for (const target of job.targets) {
    try {
      window.location.hash = hashFor(target);
      window.dispatchEvent({
        type: "hashchange",
        preventDefault() {},
        stopPropagation() {},
      });
      result.rendered += 1;
    } catch (error) {
      result.exceptions.push({
        view: target.view,
        case: target.case === undefined ? null : target.case,
        step: target.step === undefined ? null : target.step,
        error: describe(error),
      });
    }
  }
  return result;
}

function main(argv) {
  const job = JSON.parse(fs.readFileSync(argv[2], "utf8"));
  const pages = job.pages.map(runPage);
  process.stdout.write(JSON.stringify({ pages }, null, 1) + "\n");
}

if (require.main === module) {
  main(process.argv);
}

module.exports = { runPage, splitPage, Document, Window, Element, TextNode, Node };
