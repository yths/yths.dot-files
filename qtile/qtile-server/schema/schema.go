package schema

import (
	"os"
	"fmt"
	"strings"
	"strconv"

	"github.com/graphql-go/graphql"
)

type Battery struct {
	State string `json:"state"`
	Charge string `json:"charge"`
	ChargerConnected bool `json:"charger_connected"`
}

var batteryType = graphql.NewObject(graphql.ObjectConfig{
	Name: "Battery",
	Fields: graphql.Fields{
		"state": &graphql.Field{
			Type: graphql.String,
		},
		"charge": &graphql.Field{
			Type: graphql.String,
		},
		"charger_connected": &graphql.Field{
			Type: graphql.Boolean,
		},
	},
})

var rootQuery = graphql.NewObject(graphql.ObjectConfig{
	Name: "rootQuery",
	Fields: graphql.Fields{
		"battery": &graphql.Field{
			Type: batteryType,
			Description: "information about the battery",
			Resolve: func(params graphql.ResolveParams) (interface{}, error) {
				batteryState, _ := os.ReadFile("/sys/class/power_supply/BAT0/status")

				batteryChargeCurrentRaw, _ := os.ReadFile("/sys/class/power_supply/BAT0/charge_now")
				batteryChargeMaxRaw, _ := os.ReadFile("/sys/class/power_supply/BAT0/charge_full")				
				batteryChargeCurrent, _ := strconv.ParseFloat(strings.TrimRight(string(batteryChargeCurrentRaw), "\n"), 32)
				batteryChargeMax, _ := strconv.ParseFloat(strings.TrimRight(string(batteryChargeMaxRaw), "\n"), 32)
				
				chargerStateRaw, _ := os.ReadFile("/sys/class/power_supply/ADP1/online")
				chargerState, _ := strconv.ParseBool(strings.TrimRight(string(chargerStateRaw), "\n"))

				currentBattery := Battery{
					State: strings.TrimRight(string(batteryState), "\n"),
					Charge: fmt.Sprintf("%.2f %%", (batteryChargeCurrent / batteryChargeMax) * 100),
					ChargerConnected: chargerState,
				}
				return currentBattery, nil
			},
		},
	},
})

var QtileSchema, _ = graphql.NewSchema(graphql.SchemaConfig{
	Query: rootQuery,
})