package awsservices

import (
	"fmt"
	"log"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/credentials"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/textract"
	"github.com/spf13/viper"
)

var textractSession *textract.Textract

// use viper package to read .env file
// return the value of the key
func viperEnvVariable(key string) string {

	// SetConfigFile explicitly defines the path, name and extension of the config file.
	// Viper will use this and not check any of the config paths.
	// .env - It will search for the .env file in the current directory
	viper.SetConfigFile("./.env")

	// Find and read the config file
	err := viper.ReadInConfig()

	if err != nil {
		log.Fatalf("Error while reading config file %s", err)
	}

	// viper.Get() returns an empty interface{}
	// to get the underlying type of the key,
	// we have to do the type assertion, we know the underlying value is string
	// if we type assert to other type it will throw an error
	value, ok := viper.Get(key).(string)

	// If the type is a string then ok will be true
	// ok will make sure the program not break
	if !ok {
		log.Fatalf("Invalid type assertion")
	}

	return value
}

func init() {

	awsaccesskey := viperEnvVariable("awsaccesskey")
	awssecret := viperEnvVariable("awssecret")
	awstoken := viperEnvVariable("awstoken")

	textractSession = textract.New(session.Must(session.NewSession(&aws.Config{
		Region:      aws.String("ca-central-1"),
		Credentials: credentials.NewStaticCredentials(awsaccesskey, awssecret, awstoken),
	})))
}

func Extractdocumentcontent(fileinput []byte) {
	file := fileinput

	resp, err := textractSession.DetectDocumentText(&textract.DetectDocumentTextInput{
		Document: &textract.Document{
			Bytes: file,
		},
	})
	if err != nil {
		panic(err)
	}

	fmt.Println(resp)

	for i := 1; i < len(resp.Blocks); i++ {
		if *resp.Blocks[i].BlockType == "WORD" {
			fmt.Println(*resp.Blocks[i].Text)
		}
	}
}
