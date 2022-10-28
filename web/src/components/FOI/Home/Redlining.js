import React, { useRef, useEffect,useState } from 'react';
import WebViewer from '@pdftron/webviewer';

const Redlining = ({
  currentPage
}) =>{

    const viewer = useRef(null);
    const pdffile = '/files/PDFTRON_about.pdf'
    const [instance, setInstance] = useState(null)
    const [documentViewer, setDocumentViewer] = useState(null)

    const [storedannotations, setstoreannotations] = useState(localStorage.getItem("storedannotations") || [])
    // if using a class, equivalent of componentDidMount
    useEffect(() => {
      WebViewer(
        {
          path: '/webviewer',
          preloadWorker: 'pdf',
          initialDoc: pdffile,
          fullAPI: true,
          enableRedaction: true,
        },
        viewer.current,
      ).then((instance) => {


        const { documentViewer, annotationManager, Annotations ,  PDFNet , Search  } = instance.Core;
        PDFNet.initialize();


        let _annotmanager = documentViewer.getAnnotationManager();




        documentViewer.addEventListener('documentLoaded', () => {

          PDFNet.initialize(); // Only needs to be initialized once

          var _savedannotations = localStorage.getItem("savedannotations")
          // var _savedannotations = `<?xml version="1.0" encoding="UTF-8" ?><xfdf xmlns="http://ns.adobe.com/xfdf/" xml:space="preserve"><annots><highlight page="4" rect="36,632.174,285.874,723.396" color="#FFCD45" flags="print" name="7b669613-e348-1e38-b3fe-cf2db942af7d" title="Guest" subject="Highlight" date="D:20221025142712-07'00'" creationdate="D:20221025142711-07'00'" coords="77.016,723.3961468749999,257.2056,723.3961468749999,77.016,712.1543499999999,257.2056,712.1543499999999,36,707.4001468749999,237.65760000000006,707.4001468749999,36,696.1583499999999,237.65760000000006,696.1583499999999,36,691.4041468749999,271.3188,691.4041468749999,36,680.1623499999998,271.3188,680.1623499999998,36,675.4081468749999,285.87360000000007,675.4081468749999,36,664.1663499999999,285.87360000000007,664.1663499999999,36,659.6701058593749,255.204,659.6701058593749,36,648.1703499999999,255.204,648.1703499999999,36,643.6741058593749,125.60280000000002,643.6741058593749,36,632.1743499999999,125.60280000000002,632.1743499999999"><trn-custom-data bytes="{&quot;trn-annot-preview&quot;:&quot;engaging PDF at a low level, where\nobjects are defined in PDF byte code —\nwith unique byte offsets for different objects,\nmaking it difficult for devs unfamiliar with PDF’s\ninner workings to parse and manage these\nobjects correctly.&quot;}"/></highlight><text page="4" rect="148.710,472.260,179.710,503.260" color="#FFCD45" flags="print,nozoom,norotate" name="961b7420-383d-a039-4d9f-2aea098f585b" title="Guest" subject="Note" date="D:20221025144217-07'00'" creationdate="D:20221025142716-07'00'" icon="Comment" statemodel="Review"><trn-custom-data bytes="{&quot;trn-mention&quot;:&quot;{\&quot;contents\&quot;:\&quot;test\\n\&quot;,\&quot;ids\&quot;:[]}&quot;,&quot;trn-attachments&quot;:&quot;[]&quot;}"/><contents>test
          // </contents><contents-richtext><body><p><span>test
          // </span></p></body></contents-richtext></text><ink page="4" rect="323.560,393.710,538.310,712.670" color="#E44234" flags="print" name="2aee2f8a-cddd-32a0-8a7a-c187b6671b7d" title="Guest" subject="Free Hand" date="D:20221025144430-07'00'" creationdate="D:20221025144224-07'00'"><trn-custom-data bytes="{&quot;trn-mention&quot;:&quot;{\&quot;contents\&quot;:\&quot;test\\n\&quot;,\&quot;ids\&quot;:[]}&quot;}"/><contents>test
          // </contents><inklist><gesture>324.56,610.72;325.64,610.72;327.82,610.72;329.99,609.64;332.16,607.47;337.58,603.13;344.1,597.7;353.87,592.27;362.55,587.9300000000001;373.41,583.59;382.09,579.25;390.77,574.9;396.2,571.65;400.54,569.48;402.71,568.39;404.88,567.31;405.97,567.31;405.97,566.22;408.14,564.05;411.4,564.05;415.74,560.79;420.08,557.54;424.42,555.36;427.68,553.19;432.02,551.02;434.19,549.94;437.45,547.77;439.62,546.6800000000001;441.79,546.6800000000001;442.88,545.6;442.88,544.51;443.96,544.51;445.05,544.51;446.13,544.51</gesture><gesture>433.11,676.94;434.19,676.94;434.19,675.85;434.19,672.6;434.19,670.4300000000001;434.19,667.17;434.19,663.91;430.94,659.5699999999999;429.85,656.31;426.59,653.06;423.34,649.8;420.08,646.55;417.91,644.37;416.82,643.29;414.65,642.2;413.57,641.12;411.4,640.03;410.31,638.95;409.23,638.95;408.14,637.86;404.88,636.78;402.71,636.78;400.54,635.69;398.37,634.61;396.2,633.52;394.03,633.52;392.94,632.4300000000001;390.77,631.35;388.6,631.35;386.43,631.35;384.26,630.26;381,630.26;377.75,630.26;374.49,630.26;371.23,630.26;365.81,630.26;359.29,630.26;353.87,631.35;350.61,632.4300000000001;347.35,632.4300000000001;344.1,633.52;341.93,634.61;340.84,634.61</gesture><gesture>489.55,711.67;489.55,710.59;490.64,701.91;491.72,693.22;492.81,683.45;493.89,671.51;496.07,662.83;497.15,655.23;498.24,647.63;499.32,640.03;500.41,633.52;500.41,630.26;500.41,627.01;500.41,623.75;501.49,621.58;501.49,618.3199999999999;501.49,615.0699999999999;502.58,612.9;502.58,610.72;503.66,609.64;503.66,606.38;503.66,604.21;504.75,602.04;505.83,599.87;506.92,597.7;509.09,594.44;510.18,592.27;511.26,591.19;513.43,587.9300000000001;515.6,585.76;517.77,583.59;519.95,581.42;523.2,579.25;524.29,578.16;526.46,575.99;528.63,574.9;529.72,572.73;531.89,571.65;531.89,570.56;532.97,570.56;532.97,569.48;534.06,569.48;535.14,569.48;536.23,569.48;537.31,569.48</gesture><gesture>347.35,395.8;349.53,395.8;350.61,397.97;352.78,403.4;356.04,412.08;360.38,422.94;363.64,432.71;367.98,440.3;372.32,447.9;376.66,454.42;381,458.76;384.26,462.01;388.6,466.36;392.94,469.61;398.37,472.87;403.8,473.95;409.23,476.12;415.74,477.21;422.25,479.38;427.68,480.47;434.19,481.55;437.45,482.64;439.62,482.64;440.71,482.64;441.79,482.64;442.88,482.64;445.05,480.47;449.39,478.3;451.56,475.04;453.73,472.87;458.07,468.53;461.33,465.27;463.5,460.93;466.76,458.76;468.93,455.5;472.18,451.16;475.44,444.65;478.7,437.05;480.87,429.45;481.95,422.94;483.04,414.25;484.12,406.65;485.21,401.23;485.21,397.97;485.21,395.8;486.3,394.71;484.12,394.71;478.7,396.88;472.18,400.14;465.67,403.4;461.33,405.57;459.16,407.74;456.99,409.91;456.99,412.08;456.99,415.34;456.99,420.77;458.07,427.28;462.42,433.79;499.32,453.33;509.09,455.5;518.86,456.59;525.37,457.67;534.06,458.76;536.23,459.84;536.23,463.1;535.14,469.61;535.14,475.04;532.97,486.98;529.72,500.01;526.46,510.86;521.03,520.63;518.86,524.97;514.52,527.14;512.35,529.31;511.26,530.4;509.09,530.4;508.01,530.4;504.75,530.4;501.49,530.4;498.24,529.31;494.98,528.23;491.72,527.14;489.55,527.14;488.47,527.14;487.38,526.06;487.38,528.23;488.47,528.23;488.47,529.31</gesture></inklist></ink></annots></xfdf>`
          // const _annotations = _annotmanager.importAnnotationCommand(_savedannotations)
          const _annotations = _annotmanager.importAnnotations(_savedannotations)
              _annotations.then(_annotation => {

              _annotmanager.redrawAnnotation(_annotation);

            });
          documentViewer.displayPageLocation(5, 0, 0)
          setDocumentViewer(documentViewer)


        });



        documentViewer.addEventListener('pageComplete', (pageNumber, canvas) => {
          // here it's guaranteed that page {pageNumber} is fully rendered
          // you can get or set pixels on the canvas, etc

          console.log(`Page Loaded # ${pageNumber}`)
        })






        // later save the annotation data as transaction command for every change
      annotationManager.addEventListener('annotationChanged', (annotations, action, info) => {
        // If the event is triggered by importing then it can be ignored
        // This will happen when importing the initial annotations
        // from the server or individual changes from other users
        if (info.imported) return;

        console.log(action)

        annotations.forEach((annot) => {
          console.log('annotation page number', annot.PageNumber);
          console.log(annot)
          console.log(JSON.stringify(annot))
        });

        let _annotationtring = _annotmanager.exportAnnotations({annotList: annotations, useDisplayAuthor: true})
        let allannotations = _annotmanager.exportAnnotations({annotList: _annotmanager.getAnnotationsList(), useDisplayAuthor: true})
        // let _annotationtring = _annotmanager.exportAnnotationCommand()
        _annotationtring.then(astr=>{
          console.log(astr)
          // xmlstring = new DOMParser().parseFromString(astr,"text/xml").getElementsByTagName("annots")[0].firstChild.getAttr

        })
        allannotations.then(astr=>{
          console.log(astr)
          // localStorage.setItem("savedannotations",astr)
        })

      });



      });
    }, []);

    useEffect(() => {
      console.log("here")
      documentViewer?.displayPageLocation(currentPage, 0, 0)
    }, [currentPage])

    const gotopage = () => {
      documentViewer.displayPageLocation(5, 0, 0)
    }

    return (
          <div>
            {/* <button onClick={gotopage}>Click here</button> */}
            <div className="webviewer" ref={viewer}></div>
          </div>
      );

}

export default Redlining;