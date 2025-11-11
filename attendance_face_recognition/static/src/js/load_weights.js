odoo.define('attendance_face_recognition.load_weights', function (require) {
    "use strict";

    var ajax = require('web.ajax');
    var session = require("web.session");

    console.log("session",  session);

    $(document).ready(function () {
        
        LoadWeights().then(async function(){
            prepareFaceDetector();
        });

        async function LoadWeights() {
            return Promise.all([
                await ajax.loadLibs(
                    faceapi.nets.tinyFaceDetector.loadFromUri('/attendance_face_recognition/static/src/lib/weights'),
                    faceapi.nets.faceLandmark68Net.loadFromUri('/attendance_face_recognition/static/src/lib/weights'),
                    faceapi.nets.faceLandmark68TinyNet.loadFromUri('/attendance_face_recognition/static/src/lib/weights'),
                    faceapi.nets.faceRecognitionNet.loadFromUri('/attendance_face_recognition/static/src/lib/weights'),
                    faceapi.nets.faceExpressionNet.loadFromUri('/attendance_face_recognition/static/src/lib/weights'),
                )
            ])
        }

        async function prepareFaceDetector() {
            const options = getFaceDetectorOptions();   
            const useTinyModel = true ;
            return new Promise(function(){
                let base_image = new Image();
                base_image.src = "/attendance_face_recognition/static/src/img/startFaceDetect.jpg";                
                base_image.onload = async function() {
                    var has_Detection_model = isFaceDetectionModelLoaded();
                    var has_Recognition_model = isFaceRecognitionModelLoaded();
                    var has_Landmark_model = isFaceLandmarkModelLoaded();
                
                    if (has_Detection_model && has_Recognition_model && has_Landmark_model){
                        await faceapi.detectSingleFace(base_image, options).withFaceLandmarks().withFaceDescriptor().run().then(res => {});;                        
                    }else{
                        return setTimeout(() => prepareFaceDetector())
                    } 
                }
            });
        }
        
        function getFaceDetectorOptions() {
            let inputSize = 384; // by 32, common sizes are 128, 160, 224, 320, 416, 512, 608,
            let scoreThreshold = 0.5;
            return new faceapi.TinyFaceDetectorOptions(); //{inputSize, scoreThreshold }
        }

        function getCurrentFaceDetectionNet() {
            return faceapi.nets.tinyFaceDetector;
        }

        function isFaceDetectionModelLoaded() {
            return !!getCurrentFaceDetectionNet().params
        }

        function getCurrentFaceRecognitionNet () {
            return faceapi.nets.faceRecognitionNet;
        }

        function isFaceRecognitionModelLoaded() {
            return !!getCurrentFaceRecognitionNet().params
        }

        function getCurrentFaceLandmarkNet () {
            return faceapi.nets.faceLandmark68Net;
        }

        function isFaceLandmarkModelLoaded() {
            return !!getCurrentFaceLandmarkNet().params
        }
    });
});
    
