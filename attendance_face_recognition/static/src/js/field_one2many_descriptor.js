/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { useX2ManyCrud, useOpenX2ManyRecord, X2ManyFieldDialog } from "@web/views/fields/relational_utils";
import { makeDeferred } from '@mail/utils/deferred';
import { blockUI, unblockUI } from "web.framework";

patch(X2ManyFieldDialog.prototype, "one2many_description", {
    setup() {
        this._super(...arguments);
    },

    load_models: function(){
        var self = this;
        self.load_label = makeDeferred();
        return Promise.all([
            // faceapi.nets.ssdMobilenetv1.loadFromUri('/attendance_face_recognition/static/src/lib/weights'), //Using tinyFaceDetector
            faceapi.nets.tinyFaceDetector.loadFromUri('/attendance_face_recognition/static/src/lib/weights'),
            faceapi.nets.faceLandmark68Net.loadFromUri('/attendance_face_recognition/static/src/lib/weights'),
            faceapi.nets.faceLandmark68TinyNet.loadFromUri('/attendance_face_recognition/static/src/lib/weights'),
            faceapi.nets.faceRecognitionNet.loadFromUri('/attendance_face_recognition/static/src/lib/weights'),
            faceapi.nets.faceExpressionNet.loadFromUri('/attendance_face_recognition/static/src/lib/weights'),
        ])
    },

    async save({ saveAndNew }) {
        if(this.record.resModel === 'hr.employee.faces'){
            var self = this;
            var image = this.record.data.image || false;            
            if (image){
                var image = $('#face_image div img')[0];        
                self.getDescriptor(image);
            }
        }else{
            return this._super(...arguments);
        }
    },

    async getDescriptor(image){
        var self = this;
        blockUI();
        self.load_models().then(async function(){
            self.load_label.resolve();
            var has_Detection_model = self.isFaceDetectionModelLoaded();
            var has_Recognition_model = self.isFaceRecognitionModelLoaded();
            var has_Landmark_model = self.isFaceLandmarkModelLoaded();            
            if (has_Detection_model && has_Recognition_model && has_Landmark_model){
                var img = document.createElement('img');
                img.src= image.src;
                // SsdMobilenetv1Options //Using tinyFaceDetector
                await await faceapi.detectSingleFace(img , new faceapi.TinyFaceDetectorOptions())
                .withFaceLandmarks().withFaceDescriptor().then(function(result){
                    if (result != undefined && result && result.descriptor){
                        var descriptor = self.formatDescriptor(result.descriptor);
                        self.updateDescriptor(descriptor);
                        unblockUI();
                    }else{
                        unblockUI();
                    }
                });
            }else{
                return setTimeout(() => self.getDescriptor(image))
            }
        })
    },
    async updateDescriptor(descriptor){
        var self = this;
        this.record.update({'descriptor': descriptor});
        if (await this.record.checkValidity()) {
            const saved = (await this.props.save(this.record, {})) || this.record;
        } else {
            return false;
        }
        this.props.close();
        return true;
    },
    formatDescriptor(descriptor) {
        var self = this;
        let result = window.btoa(String.fromCharCode(...(new Uint8Array(descriptor.buffer))));
        return result;
    },
    getCurrentFaceDetectionNet() {
        var self = this;
        // ssdMobilenetv1 //Using tinyFaceDetector
        return faceapi.nets.tinyFaceDetector;
    },

    isFaceDetectionModelLoaded() {
        var self = this;
        return !!self.getCurrentFaceDetectionNet().params
    },

    getCurrentFaceRecognitionNet () {
        var self = this;
        return faceapi.nets.faceRecognitionNet;
    },

    isFaceRecognitionModelLoaded() {
        var self = this;
        return !!self.getCurrentFaceRecognitionNet().params
    },

    getCurrentFaceLandmarkNet() {
        var self = this;
        return faceapi.nets.faceLandmark68Net;
    },

    isFaceLandmarkModelLoaded() {
        var self = this;
        return !!self.getCurrentFaceLandmarkNet().params
    },
    
});