odoo.define('attendance_face_recognition.attendance_face_recognition', function (require) {
    "use strict";

    var core = require('web.core');

    var MyAttendances = require('hr_attendance.my_attendances');
    var KioskMode = require('hr_attendance.kiosk_mode');
    
    var Widget = require("web.Widget");
    var session = require("web.session");   
    var Dialog = require('web.Dialog');
    
    var _t = core._t;
    var QWeb = core.qweb;

    MyAttendances.include({
        init: function (parent, action) {
            this._super.apply(this, arguments);
            this.load_models = this.load_models();
            this.labeledFaceDescriptors = [];
            this.load_label = $.Deferred();
        },  

        load_models: function(){
            var self = this;
            return Promise.all([
                faceapi.nets.tinyFaceDetector.loadFromUri('/attendance_face_recognition/static/src/lib/weights'),
                faceapi.nets.faceLandmark68Net.loadFromUri('/attendance_face_recognition/static/src/lib/weights'),
                faceapi.nets.faceLandmark68TinyNet.loadFromUri('/attendance_face_recognition/static/src/lib/weights'),
                faceapi.nets.faceRecognitionNet.loadFromUri('/attendance_face_recognition/static/src/lib/weights'),
                faceapi.nets.faceExpressionNet.loadFromUri('/attendance_face_recognition/static/src/lib/weights'),
            ]).then(function(){
                self.prepareFaceDetector();
            });
        },

        start: function(){
            var self = this;
            return $.when(self.load_models, this._super.apply(this, arguments)).then(function(){
                self.loadLabeledImages();
                self.$el.find('.face_recognition_status').removeClass('d-none').addClass('face_recognition_main_on');
            });
        },

        loadLabeledImages:  function(){
            var self = this;
            return this._rpc({
                route: '/attendance_face_recognition/loadLabeledImages/'
            }).then(async function (data) {
                self.labeledFaceDescriptors = await Promise.all(
                    data.map((data, i) => {  
                    const descriptors = [];
                    for (var i = 0; i < data.descriptors.length; i++) {
                        if (data.descriptors[i]){
                            descriptors.push(new Float32Array(new Uint8Array([...window.atob(data.descriptors[i])].map(d => d.charCodeAt(0))).buffer));
                        }
                    }
                    return new faceapi.LabeledFaceDescriptors(data.label.toString(), descriptors);
                }));
                self.load_label.resolve();
            })
        },

        prepareFaceDetector: async function() {
            var self = this;
            return new Promise(function(){
                let base_image = new Image();
                base_image.src = "/attendance_face_recognition/static/src/img/startFaceDetect.jpg";                
                base_image.onload = async function() {
                    var has_Detection_model = self.isFaceDetectionModelLoaded();
                    var has_Recognition_model = self.isFaceRecognitionModelLoaded();
                    var has_Landmark_model = self.isFaceLandmarkModelLoaded();
                
                    if (has_Detection_model && has_Recognition_model && has_Landmark_model){
                        await faceapi.detectSingleFace(base_image, new faceapi.TinyFaceDetectorOptions())
                            .withFaceLandmarks()
                            .withFaceDescriptor()
                            .run().then(res => {});;                        
                    }else{
                        return setTimeout(() => self.prepareFaceDetector())
                    } 
                }
            });
        },

        update_attendance: function () {
            var self = this;
            if(session.attendance_face_recognition){
                if (self.labeledFaceDescriptors && self.labeledFaceDescriptors.length != 0){
                    var matchedEmployee = new FaceRecognitionDialog(this, {
                        'labeledFaceDescriptors': self.labeledFaceDescriptors,
                    }).open();
                }else{
                    self.displayNotification({ message: _t('Detection Failed: Resource not found, Please add it to your employee profile.'), type: 'danger' });
                }
            }else{
                self._super();
            }
        },

        _update_face_attendance: _.debounce(function (employee_id, img) {
            var self = this;
            this._rpc({
                model: 'hr.employee',
                method: 'attendance_manual',
                args: [[parseInt(employee_id)], 'hr_attendance.hr_attendance_action_my_attendances', null , img],
            })
            .then(function (result) {
                if (result.action) {
                    self.do_action(result.action);
                    
                } else if (result.warning) {
                    self.displayNotification({message: result.warning, type: 'danger'});
                }
            });
        }, 200, true),

        getCurrentFaceDetectionNet: function() {
            return faceapi.nets.tinyFaceDetector;
        },

        isFaceDetectionModelLoaded: function() {
            return !!this.getCurrentFaceDetectionNet().params
        },

        getCurrentFaceRecognitionNet:function () {
            return faceapi.nets.faceRecognitionNet;
        },

        isFaceRecognitionModelLoaded: function() {
            return !!this.getCurrentFaceRecognitionNet().params
        },

        getCurrentFaceLandmarkNet: function() {
            return faceapi.nets.faceLandmark68Net;
        },

        isFaceLandmarkModelLoaded: function() {
            return !!this.getCurrentFaceLandmarkNet().params
        },
    });

    KioskMode.include({
        events: _.extend(KioskMode.prototype.events, {
            "click .o_hr_kiosk_face_recognition":  _.debounce(function() {
                this.update_kiosk_attendance();
            }, 200, true),
        }),
        init: function (parent, action) {
            this._super.apply(this, arguments);
            this.is_face_recognition_enabled = session.kiosk_face_recognition;

            this.load_models = this.load_models();
            this.labeledFaceDescriptors = [];
            this.load_label = $.Deferred();
        },
        load_models: function(){
            var self = this;
            return Promise.all([
                faceapi.nets.tinyFaceDetector.loadFromUri('/attendance_face_recognition/static/src/lib/weights'),
                faceapi.nets.faceLandmark68Net.loadFromUri('/attendance_face_recognition/static/src/lib/weights'),
                faceapi.nets.faceLandmark68TinyNet.loadFromUri('/attendance_face_recognition/static/src/lib/weights'),
                faceapi.nets.faceRecognitionNet.loadFromUri('/attendance_face_recognition/static/src/lib/weights'),
                faceapi.nets.faceExpressionNet.loadFromUri('/attendance_face_recognition/static/src/lib/weights'),
            ]).then(function(){
                self.prepareFaceDetector();
            });
        },
        start: function () {            
            var self= this;
            return $.when(self.load_models, this._super.apply(this, arguments)).then(function(){
                self.loadLabeledImages();
                self.$el.find('.face_recognition_status').removeClass('d-none').addClass('face_recognition_main_on');
            });
        },
        loadLabeledImages:  function(){
            var self = this;
            return this._rpc({
                route: '/attendance_face_recognition/loadLabeledImages/'
            }).then(async function (data) {
                self.labeledFaceDescriptors = await Promise.all(
                    data.map((data, i) => {  
                    const descriptors = [];
                    for (var i = 0; i < data.descriptors.length; i++) {
                        if (data.descriptors[i]){
                            descriptors.push(new Float32Array(new Uint8Array([...window.atob(data.descriptors[i])].map(d => d.charCodeAt(0))).buffer));
                        }
                    }
                    return new faceapi.LabeledFaceDescriptors(data.label.toString(), descriptors);
                }));
                self.load_label.resolve();
            })
        },

        prepareFaceDetector: async function() {
            var self = this;
            return new Promise(function(){
                let base_image = new Image();
                base_image.src = "/attendance_face_recognition/static/src/img/startFaceDetect.jpg";                
                base_image.onload = async function() {
                    var has_Detection_model = self.isFaceDetectionModelLoaded();
                    var has_Recognition_model = self.isFaceRecognitionModelLoaded();
                    var has_Landmark_model = self.isFaceLandmarkModelLoaded();
                
                    if (has_Detection_model && has_Recognition_model && has_Landmark_model){
                        await faceapi.detectSingleFace(base_image, new faceapi.TinyFaceDetectorOptions())
                            .withFaceLandmarks()
                            .withFaceDescriptor()
                            .run().then(res => {});;                        
                    }else{
                        return setTimeout(() => self.prepareFaceDetector())
                    } 
                }
            });
        },

        update_kiosk_attendance: function () {
            var self = this;
            if(session.kiosk_face_recognition){
                if (self.labeledFaceDescriptors && self.labeledFaceDescriptors.length != 0){
                    var matchedEmployee = new FaceRecognitionDialog(this, {
                        'labeledFaceDescriptors': self.labeledFaceDescriptors,
                    }).open();
                }else{
                    self.displayNotification({ message: _t('Detection Failed: Resource not found, Please add it to your employee profile.'), type: 'danger' });
                }
            }       
        },

        _update_face_attendance: _.debounce(function (employee_id, img) {
            var self = this;
            this._rpc({
                model: 'hr.employee',
                method: 'attendance_kiosk_recognition',
                args: [[parseInt(employee_id)], img],
            })
            .then(function (result) {
                if (result.action) {
                    self.do_action(result.action);
                    
                } else if (result.warning) {
                    self.displayNotification({message: result.warning, type: 'danger'});
                }
            });
        }, 200, true),

        getCurrentFaceDetectionNet: function() {
            return faceapi.nets.tinyFaceDetector;
        },

        isFaceDetectionModelLoaded: function() {
            return !!this.getCurrentFaceDetectionNet().params
        },

        getCurrentFaceRecognitionNet:function () {
            return faceapi.nets.faceRecognitionNet;
        },

        isFaceRecognitionModelLoaded: function() {
            return !!this.getCurrentFaceRecognitionNet().params
        },

        getCurrentFaceLandmarkNet: function() {
            return faceapi.nets.faceLandmark68Net;
        },

        isFaceLandmarkModelLoaded: function() {
            return !!this.getCurrentFaceLandmarkNet().params
        },
    });


    var FaceRecognitionDialog = Dialog.extend({
        template: "FaceRecognitionDialog",
        events: _.extend({}, Dialog.events, {
            'change select#videoSource': 'getStream',
            'click .close': '_onDestroy',
        }),
        init: function (parent, options) {
            options = options || {};
            this._super(parent, _.extend({
                size: 'medium',
                title: _t('Face Recognition'),
                buttons: [
                    {
                        text: _t("Close"), classes: 'btn-secondary captureClose', close: true, click: this._onDestroy.bind(this)
                    }
                ],
            }, this.options));

            this.match_label = '';
            this.match_employee_id = false;
            this.is_update_attendance = false;
            this.parent = parent;
            this.descriptors = options.labeledFaceDescriptors;
            this.match_count = [];
        },
        start: async function () {
            var self = this;
            self.opened().then(function () {
                self.$el.find('.video-controls').removeClass('d-none');
                self.getStream().then(self.getDevices.bind(self)).then(self.gotDevices.bind(self));
            });
            return this._super.apply(this, arguments);
        },
        getStream: async function () {
            var self = this;
            if (window.stream) {
                window.stream.getTracks().forEach(track => {
                    track.stop();
                });
            }
            var videoSelect = self.$el.find('select#videoSource').get(0);
            const videoSource = videoSelect.value;
            const constraints = {
                video: { deviceId: videoSource ? { exact: videoSource } : undefined }
            };
            return await navigator.mediaDevices.getUserMedia(constraints)
                .then(self.gotStream.bind(self))
                .catch(self.handleError.bind(self));;
        },

        getDevices: function () {
            var self = this;
            return navigator.mediaDevices.enumerateDevices();
        },

        gotDevices: function (deviceInfos) {
            var self = this;
            var videoSelect = self.$el.find('select#videoSource').get(0);
            window.deviceInfos = deviceInfos;
            for (const deviceInfo of deviceInfos) {
                const option = document.createElement('option');
                option.value = deviceInfo.deviceId;
                if (deviceInfo.kind === 'videoinput') {
                    option.text = deviceInfo.label || "Camera" + (videoSelect.length + 1) + "";
                    videoSelect.appendChild(option);
                }
            }
        },

        gotStream: function (stream) {
            var self = this;
            var videoElement = self.$el.find('#video').get(0);
            var videoSelect = self.$el.find('select#videoSource').get(0);
            window.stream = stream;
            videoSelect.selectedIndex = [...videoSelect.options].findIndex(option => option.text === stream.getVideoTracks()[0].label);
            videoElement.srcObject = stream;
            videoElement.play().then(self.onLoadStream.bind(self))     
        },
        handleError: function (error) {
            var self = this;
            console.log('Error: ', error);
        },
        _onDestroy: function () {            
            this.destroy();
        },
        destroy: function () {
            if (this.isDestroyed()) {
                return;
            }
            if (this.intervalID) {
                clearInterval(this.intervalID);
            }
            if (window.stream) {
                window.stream.getTracks().forEach(track => {
                    track.stop();
                });
            }
            this._super.apply(this, arguments);
        },
        onLoadStream: async function () {
            var self = this;
            if (this.intervalID) {
                clearInterval(this.intervalID);
            }            
            var video = self.$el.find("#video").get(0);
            var canvas = self.$el.find("#canvas").get(0);
            self.FaceDetector(video, canvas);        
        },
        
        FaceDetector: async function (video, canvas) {
            var self = this;

            if (video.paused || video.ended || !this.isFaceDetectionModelLoaded() || self.descriptors.length === 0) {
                return setTimeout(() => this.FaceDetector())
            }

            var options = this.getFaceDetectorOptions();
            var useTinyModel = true;
            var maxDescriptorDistance = 0.45;

            var displaySize = { width: video.offsetWidth, height: video.offsetHeight };
            faceapi.matchDimensions(canvas, displaySize);
            self.intervalID = setInterval(async () => {
                canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
                const detections = await faceapi.detectSingleFace(video, options)
                    .withFaceLandmarks()
                    .withFaceDescriptor();
                if (detections) {
                    if(displaySize.width == 0 || displaySize.height == 0){
                        clearInterval(self.intervalID);
                        return
                    }                
                    const resizedDetections = faceapi.resizeResults(detections, displaySize)
                    faceapi.draw.drawDetections(canvas, resizedDetections)
                    faceapi.draw.drawFaceLandmarks(canvas, resizedDetections)

                    if (resizedDetections && Object.keys(resizedDetections).length > 0) {
                        var faceMatcher = new faceapi.FaceMatcher(self.descriptors, maxDescriptorDistance);
                        const result = faceMatcher.findBestMatch(resizedDetections.descriptor);

                        if (result && result._label != 'unknown') {
                            if (self.match_count.lenght != 'undefined') {
                                self.match_count.push(result._label);
                            } else if (self.match_count.includes(result._label)) {
                                self.match_count.push(result._label);
                            } else {
                                self.match_count = [];
                            }

                            self.match_employee_id = result._label;
                            var label = self.getName(self.match_employee_id);

                            if (label) {
                                const box = resizedDetections.detection.box;
                                const drawBox = new faceapi.draw.DrawBox(box, { label: label.toString() });
                                drawBox.draw(canvas);
                            }

                            if (self.match_label && self.match_employee_id && self.match_count.length > 2) {
                                clearInterval(self.intervalID);
                                if (!self.intervalId) {
                                    var image = self.$el.find("#image").get(0);
                                    image.width = $(video).width();
                                    image.height = $(video).height();
                                    image.getContext('2d').drawImage(video, 0, 0);
                                    var img64 = image.toDataURL("image/jpeg");
                                    img64 = img64.replace(/^data:image\/(png|jpg|jpeg);base64,/, "");
                                    self.update_attendance(self.match_employee_id, img64);
                                }
                            }
                        }
                    }
                }
            }, 200);
        },

        update_attendance: function (employee_id, img) {
            var self = this;
            if (!self.intervalId && !self.is_update_attendance) {
                self.parent._update_face_attendance(employee_id, img);
                self.is_update_attendance = true;
                self.match_label = '';
                self.match_count = [];
                self.match_employee_id = false;
                self._onDestroy();
            }
        },

        getName: function (employee_id) {
            var self = this;
            var prom = Promise.resolve();
            prom.then(function () {
                if (employee_id !== 'unknown') {
                    self._rpc({
                        route: `/attendance_face_recognition/getName/${employee_id}/`
                    })
                        .then(function (result) {
                            if (result) {
                                self.match_label = result;
                            }
                        })
                }
            })
            return self.match_label;
        },

        getFaceDetectorOptions: function() {
            let inputSize = 384; // by 32, common sizes are 128, 160, 224, 320, 416, 512, 608,
            let scoreThreshold = 0.5;
            return new faceapi.TinyFaceDetectorOptions(); // {inputSize, scoreThreshold }
        },

        getCurrentFaceDetectionNet: function() {
            return faceapi.nets.tinyFaceDetector;
        },

        isFaceDetectionModelLoaded: function() {
            return !!this.getCurrentFaceDetectionNet().params
        },
    });
    return FaceRecognitionDialog;

});