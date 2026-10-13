
(function(){
  "use strict";
  document.documentElement.classList.remove("no-js");
  function each(selector, root){ return Array.prototype.slice.call((root || document).querySelectorAll(selector)); }
  function copyText(text, done){
    if (navigator.clipboard && navigator.clipboard.writeText){ navigator.clipboard.writeText(text).then(function(){ done(true); }, function(){ done(false); }); }
    else { done(false); }
  }
  var OK = "已复制", NO = "请手动选择复制";
  each(".code .cbtn").forEach(function(b){
    var label = b.textContent;
    b.addEventListener("click", function(){
      copyText(b.parentNode.querySelector("pre").textContent, function(ok){ b.textContent = ok ? OK : NO; setTimeout(function(){ b.textContent = label; }, 1600); });
    });
  });
  var cb = document.getElementById("copy-cmds");
  if (cb){
    var cl = cb.textContent;
    cb.addEventListener("click", function(){
      copyText(each(".term code").map(function(c){ return c.textContent; }).join("\n"), function(ok){ cb.textContent = ok ? OK : NO; setTimeout(function(){ cb.textContent = cl; }, 1600); });
    });
  }
  var box = document.getElementById("film-box"), video = document.getElementById("film-video");
  if (box && video){ video.addEventListener("loadedmetadata", function(){ box.className += " ready"; }); }

  each(".acc-btn").forEach(function(b){
    b.addEventListener("click", function(){ b.setAttribute("aria-expanded", b.getAttribute("aria-expanded") === "true" ? "false" : "true"); });
  });
  if (location.hash){
    var tgt = document.getElementById(location.hash.slice(1));
    if (tgt && tgt.classList.contains("acc-item")){ tgt.querySelector(".acc-btn").setAttribute("aria-expanded", "true"); }
  }
  // ---------------------------------------------------------------------------
  // Motion. Everything below is decoration: with reduced motion asked for, or
  // without this script, the page reads the same.
  // ---------------------------------------------------------------------------
  var root = document.documentElement;
  var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var fine = window.matchMedia && window.matchMedia("(pointer: fine)").matches;

  // The queue sits in a disclosure; a link to it opens it.
  function openQueue(){
    var d = document.getElementById("queue-details");
    if (d && !d.open){ d.open = true; }
  }
  if (location.hash === "#queue-section"){ openQueue(); }

  if (!still){
    // 1. Rise-in: blocks fade up a few pixels as they enter, three at a time.
    if ("IntersectionObserver" in window){
      var targets = each("[data-rise]");
      var seen = [];
      targets.forEach(function(el){
        var p = el.parentNode, i = seen.indexOf(p), n;
        if (i < 0){ seen.push(p); p.__n = 0; }
        n = p.__n++;
        el.style.transitionDelay = ((n % 3) * 80) + "ms";
      });
      root.classList.add("js-motion");
      var io = new IntersectionObserver(function(entries){
        entries.forEach(function(e){
          if (e.isIntersecting){ e.target.classList.add("in"); io.unobserve(e.target); }
        });
      }, {rootMargin: "0px 0px -6% 0px", threshold: 0.06});
      targets.forEach(function(el){ io.observe(el); });
    }

    // 1b. Highlight numbers count up once, the first time they come into view.
    if ("IntersectionObserver" in window){
      var counters = each("[data-count]");
      var co = new IntersectionObserver(function(entries){
        entries.forEach(function(e){
          if (!e.isIntersecting){ return; }
          co.unobserve(e.target);
          var el = e.target, end = +el.getAttribute("data-count"), t0 = null;
          if (!end){ return; }
          function tick(ts){
            if (t0 === null){ t0 = ts; }
            var k = Math.min(1, (ts - t0) / 1400);
            el.textContent = Math.round(end * (1 - Math.pow(1 - k, 3)));
            if (k < 1){ requestAnimationFrame(tick); }
          }
          el.textContent = "0";
          requestAnimationFrame(tick);
        });
      }, {threshold: 0.6});
      counters.forEach(function(el){ co.observe(el); });
    }

    // 2. Parallax: pictures drift inside their frames at a tenth of the page's speed.
    var SPEED = 0.1, MAX = 56;
    var layers = each(".art img, .art .fallback").map(function(node){
      return {node: node, frame: node.parentNode, img: node.tagName === "IMG", scale: 1};
    });
    function measure(){
      layers.forEach(function(l){
        var h = l.frame.getBoundingClientRect().height || 1;
        l.scale = l.img ? 1 + (2 * MAX + 8) / h : 1;
      });
    }

    // 3. The frame: a light runs along the window's edge level with how far down
    // the page you are, while you scroll; a click lights the edge nearest to it.
    var glow = document.getElementById("vf-glow");
    var cue = document.getElementById("vf-cue");
    var idle = null;

    // 4. The footer comes into focus as it is uncovered.
    var foot = document.getElementById("foot");

    function onFrame(){
      var vh = window.innerHeight;
      layers.forEach(function(l){
        if (!l.node.isConnected){ return; }
        var r = l.frame.getBoundingClientRect();
        if (r.bottom < -200 || r.top > vh + 200){ return; }
        var y = Math.max(-MAX, Math.min(MAX, (vh / 2 - (r.top + r.height / 2)) * SPEED));
        l.node.style.transform = "translate3d(0," + y.toFixed(1) + "px,0)" + (l.img ? " scale(" + l.scale.toFixed(3) + ")" : "");
      });
      var max = root.scrollHeight - vh;
      if (glow){ glow.style.setProperty("--sy", (8 + 84 * (max > 0 ? window.scrollY / max : 0)).toFixed(1) + "%"); }
      if (foot){
        var fr = foot.getBoundingClientRect();
        var shown = Math.max(0, Math.min(1, (vh - fr.top) / Math.min(fr.height, vh)));
        foot.style.setProperty("--fo", shown.toFixed(3));
      }
    }
    var queued = false;
    function schedule(){
      if (!queued){ queued = true; requestAnimationFrame(function(){ queued = false; onFrame(); }); }
      if (glow){
        glow.classList.add("on");
        clearTimeout(idle);
        idle = setTimeout(function(){ glow.classList.remove("on"); }, 160);
      }
    }
    if (cue){
      document.addEventListener("pointerdown", function(e){
        cue.style.setProperty("--cx", e.clientX + "px");
        cue.style.setProperty("--cy", e.clientY + "px");
        cue.classList.remove("flash"); void cue.offsetWidth; cue.classList.add("flash");
      });
    }

    // 5. Smooth scrolling for the wheel: the page eases to where the wheel sends
    // it, fast and then slow. Touch, keys and the scroll bar stay native.
    var EASE = 0.09;
    var current = window.scrollY, target = current, running = false, ours = false;
    function maxScroll(){ return root.scrollHeight - window.innerHeight; }
    function clamp(v){ return Math.max(0, Math.min(maxScroll(), v)); }
    function step(){
      var gap = target - current;
      if (Math.abs(gap) < 0.5){ current = target; running = false; }
      else { current += gap * EASE; }
      ours = true;
      window.scrollTo(0, current);
      if (running){ requestAnimationFrame(step); }
    }
    function go(to){
      target = clamp(to);
      if (!running){ running = true; current = window.scrollY; requestAnimationFrame(step); }
    }
    function scrollsItself(el, dy){
      for (; el && el !== document.body; el = el.parentElement){
        var s = getComputedStyle(el).overflowY;
        if ((s === "auto" || s === "scroll") && el.scrollHeight > el.clientHeight){
          if (dy > 0 && el.scrollTop + el.clientHeight < el.scrollHeight - 1){ return true; }
          if (dy < 0 && el.scrollTop > 0){ return true; }
        }
      }
      return false;
    }
    if (fine){
      root.style.scrollBehavior = "auto";
      window.addEventListener("wheel", function(e){
        if (e.ctrlKey || e.defaultPrevented || Math.abs(e.deltaX) > Math.abs(e.deltaY)){ return; }
        var dy = e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? window.innerHeight : 1);
        if (scrollsItself(e.target, dy)){ return; }
        e.preventDefault();
        if (!running){ target = window.scrollY; }
        go(target + dy);
      }, {passive: false});
    }
    window.addEventListener("scroll", function(){
      if (ours){ ours = false; } else if (!running){ current = target = window.scrollY; }
      schedule();
    }, {passive: true});
    window.addEventListener("keydown", function(){ running = false; });
    window.addEventListener("resize", function(){ measure(); target = clamp(target); onFrame(); });
    window.addEventListener("load", function(){ measure(); onFrame(); });
    measure(); onFrame();

    // In-page links ease to their section and move focus there.
    each('a[href^="#"]').forEach(function(a){
      a.addEventListener("click", function(e){
        var id = a.getAttribute("href").slice(1);
        if (id === "queue-section"){ openQueue(); }
        var el = id && document.getElementById(id);
        if (!el || !fine){ return; }
        e.preventDefault();
        go(el.getBoundingClientRect().top + window.scrollY - 24);
        if (history.pushState){ history.pushState(null, "", "#" + id); }
        if (!el.hasAttribute("tabindex")){ el.setAttribute("tabindex", "-1"); }
        el.focus({preventScroll: true});
      });
    });
  } else {
    each('a[href="#queue-section"]').forEach(function(a){ a.addEventListener("click", openQueue); });
  }
})();
