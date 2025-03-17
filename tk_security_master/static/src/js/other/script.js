/***
*    Copyright (C) 2023-TODAY TechKhedut (<https://www.techkhedut.com>)
*    Part of TechKhedut. See LICENSE file for full copyright and licensing details.
****/
$(".usr_pwd").on("click", function (e) {
    $($(e.target.parentElement).find('#new_pwd')[0])
        .prop("type", (i, previous) => {
            return previous === "text" ? "password" : "text";
        });
});