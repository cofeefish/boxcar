"use strict";
// takes query, curr_page, ids_per_page, total_pages as input
// returns paginator html element

function create_link(path, param_keys, param_values) {
    const url = new URL(path);
    for (let index = 0; index < param_keys.length; index++) {
        const key = param_keys[index];
        const value = param_values[index];
        url.searchParams.set(key, value);
        
    }
    const url_string = url.toString();
    return url_string;
}

function paginator(query, ids_per_page, total_pages){
    const url_str = window.location.href;
    var curr_page = new URL(url_str).searchParams.get("page");
    // normalize numbers
    total_pages = Number(total_pages);
    if (isNaN(curr_page)) curr_page = 0;
    if (isNaN(total_pages) || total_pages < 0) total_pages = 0;
    curr_page = Math.max(0, curr_page);
    console.log(curr_page)


    const nav = document.createElement('nav');
    nav.className = 'paginator';

    function makeItem(label, page, opts = {}) {
        const {disabled = false, active = false} = opts;
        if (disabled) {
            const span = document.createElement('span');
            span.className = 'paginator-item disabled';
            span.textContent = label;
            return span;
        }
        if (active) {
            const span = document.createElement('span');
            span.className = 'paginator-item active';
            span.textContent = label;
            return span;
        }
        const a = document.createElement('a');
        a.className = 'paginator-item';
        a.href = create_link(url_str, ['page'], [page]);
        a.textContent = label;
        return a;
    }

    // first / prev
    nav.appendChild(makeItem('« First', 0, {disabled: curr_page === 0}));
    nav.appendChild(makeItem('‹ Prev', curr_page - 1, {disabled: curr_page === 0}));

    // page number window
    const maxVisible = 7;
    const half = Math.floor(maxVisible / 2);
    let start = Math.max(0, curr_page - half);
    let end = Math.min(total_pages, start + maxVisible - 1);
    start = Math.max(0, end - (maxVisible - 1));
    for (let i = start; i <= end; i++) {
        nav.appendChild(makeItem((i + 1).toString(), i, {active: i === curr_page}));
    }

    // next / last
    nav.appendChild(makeItem('Next ›', curr_page + 1));
    nav.appendChild(makeItem('Last »', total_pages, {disabled: curr_page === total_pages}));

    return nav;
}

if (typeof window !== 'undefined') window.paginator = paginator;