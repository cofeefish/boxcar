"use strict";
function switchTab(index) {
    const tabs = document.getElementsByClassName('tab');
    const panels = document.getElementsByClassName('tab-panels')[0].children;
    for (let i = 0; i < tabs.length; i++) {
        if (i === index) {
            tabs[i].classList.add('active');
            panels[i].classList.remove('hidden')
        } else {
            tabs[i].classList.remove('active');
            panels[i].classList.add('hidden')
        }
    }
}