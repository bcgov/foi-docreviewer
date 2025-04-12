package services

import (
	"fmt"

	"compressionservices/models"
)

func ProcessMessage(message *models.CompressionProducerMessage) {
	fmt.Println("message:", message)
	//RecordJobStart(message)
	defer func() {
		if r := recover(); r != nil {
			fmt.Printf("Exception while processing redis message for compression, func ProcessMessage, Error: %v\n", r)
			// Convert the panic to string error if needed
			errMsg := fmt.Sprintf("%v", r)
			RecordJobEnd(message, true, errMsg)
		}
	}()
	fmt.Printf("Just before compression!!")
	//StartCompression()
	// savedocumentdetails(message, hashcode, pagecount)
	//RecordJobEnd(message, false, "")

	// updateredactionstatus(message)
	// _incompatible := strings.ToLower(message.Incompatible) == "true"
	// if !_incompatible {
	//     pageMessage := documentspagecalculatorproducerservice{}.CreatePageCalculatorProducerMessage(message, pagecount)
	//     pageJobID := pagecalculatorjobstart(pageMessage)
	//     fmt.Println("Pushed to Page Calculator Stream!!!")
	//     documentspagecalculatorproducerservice{}.ProducePageCalculatorEvent(pageMessage, pagecount, pageJobID)
	// }
}

// from .s3documentservice import gets3documenthashcode
// from .compressiondbservice import recordjobstart,recordjobend
// savedocumentdetails, recordjobstart, recordjobend, updateredactionstatus, pagecalculatorjobstart
//  from .documentspagecalculatorservice import documentspagecalculatorproducerservice
//  from models.pagecalculatorproducermessage import pagecalculatorproducermessage
// import traceback

// def processmessage(message):
//     print("message:",message)
//     recordjobstart(message)
//     try:
//         #compressrecords()
//         #hashcode, _pagecount = gets3documenthashcode(message)
//         #savedocumentdetails(message, hashcode, _pagecount)
//         recordjobend(message, False)
//         #updateredactionstatus(message)
//         #_incompatible = True if str(message.incompatible).lower() == 'true' else False
//         # if not _incompatible:
//         #     pagecalculatormessage = documentspagecalculatorproducerservice().createpagecalculatorproducermessage(message, _pagecount)
//         #     pagecalculatorjobid = pagecalculatorjobstart(pagecalculatormessage)
//         #     print("Pushed to Page Calculator Stream!!!")
//         #     documentspagecalculatorproducerservice().producepagecalculatorevent(pagecalculatormessage, _pagecount, pagecalculatorjobid)
//     except(Exception) as error:
//         print("Exception while processing redis message, func processmessage(p3), Error : {0} ".format(error))
//         recordjobend(message, True, error.args[0])
