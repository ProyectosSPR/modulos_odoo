odoo.define("attendance_face_recognition.report_menu", function (require) {
    "use strict";

    let __exports = {};
    const { registry } = require("@web/core/registry");

    function AttendanceFaceRecognition(env)  {
        return {
            type: "item",
            id: "attendance_face_recognition",
            description: env._t("AttendanceFaceRecognition"),
            callback: async function () {
                const actionDescription = await env.services.orm.call("res.users", "action_get_attendance_face_recognition");
                actionDescription.res_id = env.services.user.userId;
                env.services.action.doAction(actionDescription);
            },
            sequence: 5,
        };
    }

    registry.category("user_menuitems").add('attendance_face_recognition', AttendanceFaceRecognition, { force: true })
    return __exports;

});