/* Progressive enhancements: all documentation is readable without JavaScript. */
const isChinese = document.documentElement.lang.startsWith('zh');
const languageLink = document.querySelector('.language-switch');
let savedLanguage = null;
try { savedLanguage = localStorage.getItem('voice-agent-language'); } catch {}
if (!['en', 'zh'].includes(savedLanguage)) savedLanguage = null;
const explicitLanguage = new URLSearchParams(location.search).get('lang');
if (!isChinese && explicitLanguage !== 'en' &&
    (savedLanguage === 'zh' || (!savedLanguage && navigator.language.toLowerCase().startsWith('zh')))) {
  location.replace(new URL(`zh/${location.hash}`, location.href));
} else {
  try { localStorage.setItem('voice-agent-language', isChinese ? 'zh' : 'en'); } catch {}
}
languageLink.addEventListener('click', () => {
  try { localStorage.setItem('voice-agent-language', languageLink.dataset.language); } catch {}
  const target = new URL(languageLink.getAttribute('href'), location.href);
  target.hash = location.hash;
  languageLink.href = target.href;
});
const text = (english, chinese) => isChinese ? chinese : english;
document.documentElement.classList.add("js");

const menu = document.querySelector(".menu-toggle");
const sidebar = document.querySelector("#sidebar");
menu.addEventListener("click", () => {
	const open = menu.getAttribute("aria-expanded") !== "true";
	menu.setAttribute("aria-expanded", String(open));
	sidebar.classList.toggle("is-open", open);
});

document.addEventListener("keydown", (event) => {
	if (event.key === "Escape" && menu.getAttribute("aria-expanded") === "true") {
		menu.setAttribute("aria-expanded", "false");
		sidebar.classList.remove("is-open");
		menu.focus();
	}
});

const links = [...sidebar.querySelectorAll('a[href^="#"]')];
links.forEach((link) =>
	link.addEventListener("click", () => {
		menu.setAttribute("aria-expanded", "false");
		sidebar.classList.remove("is-open");
		const section = document.querySelector(link.getAttribute("href"));
		section.setAttribute("tabindex", "-1");
		section.focus({ preventScroll: true });
	}),
);

// Use the section nearest the top of the viewport, including long reference sections.
let scrollPending = false;
function updateActiveLink() {
	const threshold = 150;
	let active = links[0];
	links.forEach((link) => {
		if (
			document.querySelector(link.getAttribute("href")).getBoundingClientRect()
				.top <= threshold
		) {
			active = link;
		}
	});
	links.forEach((link) => {
		if (link === active) link.setAttribute("aria-current", "location");
		else link.removeAttribute("aria-current");
	});
	scrollPending = false;
}
window.addEventListener(
	"scroll",
	() => {
		if (!scrollPending) {
			scrollPending = true;
			window.requestAnimationFrame(updateActiveLink);
		}
	},
	{ passive: true },
);
updateActiveLink();

const status = document.querySelector("#copy-status");
document.querySelectorAll(".code-block").forEach((block, index) => {
	const code = block.querySelector("code");
	const button = document.createElement("button");
	button.type = "button";
	button.className = "copy-button";
	button.textContent = text("Copy", "复制");
	button.setAttribute("aria-label", text(`Copy code example ${index + 1}`, `复制代码示例 ${index + 1}`));
	button.addEventListener("click", async () => {
		try {
			await navigator.clipboard.writeText(code.textContent);
			button.textContent = text("Copied", "已复制");
			status.textContent = text(`Code example ${index + 1} copied to clipboard.`, `代码示例 ${index + 1} 已复制到剪贴板。`);
		} catch {
			const range = document.createRange();
			range.selectNodeContents(code);
			const selection = window.getSelection();
			selection.removeAllRanges();
			selection.addRange(range);
			button.textContent = text("Selected", "已选中");
			status.textContent = text("Clipboard unavailable. Code selected; use your copy shortcut.", "无法访问剪贴板。代码已选中，请使用复制快捷键。");
		}
		window.setTimeout(() => {
			button.textContent = text("Copy", "复制");
		}, 2000);
	});
	block.append(button);
});

const themeToggle = document.querySelector(".theme-toggle");
function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  themeToggle.setAttribute("aria-label", text(`Switch to ${theme === "dark" ? "light" : "dark"} theme`, `切换为${theme === "dark" ? "浅色" : "深色"}主题`));
  themeToggle.textContent = theme === "dark" ? text("Light", "浅色") : text("Dark", "深色");
}
try { setTheme(localStorage.getItem("docs-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")); } catch { setTheme("light"); }
themeToggle.addEventListener("click", () => {
  const theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  setTheme(theme);
  try { localStorage.setItem("docs-theme", theme); } catch {}
});
