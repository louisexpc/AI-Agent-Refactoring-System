
package leaderboard

import (
	"fmt"
	"sort"
)

var points = []int{25, 18, 15}

type Driver struct {
	Name    string
	Country string
}

type SelfDrivingCar struct {
	Driver
	AlgorithmVersion string
	Company          string
}

type Race struct {
	Name        string
	Results     []interface{}
	DriverNames map[interface{}]string
}

func NewRace(name string, results []interface{}) *Race {
	r := &Race{
		Name:        name,
		Results:     results,
		DriverNames: make(map[interface{}]string),
	}
	for _, driver := range results {
		switch d := driver.(type) {
		case Driver:
			r.DriverNames[driver] = d.Name
		case SelfDrivingCar:
			r.DriverNames[driver] = fmt.Sprintf("Self Driving Car - %s (%s)", d.Company, d.AlgorithmVersion)
		}
	}
	return r
}

func (r *Race) Points(driver interface{}) int {
	for i, d := range r.Results {
		if d == driver {
			if i < len(points) {
				return points[i]
			}
		}
	}
	return 0
}

func (r *Race) DriverName(driver interface{}) string {
	return r.DriverNames[driver]
}

type Leaderboard struct {
	Races []*Race
}

func NewLeaderboard(races []*Race) *Leaderboard {
	return &Leaderboard{Races: races}
}

func (l *Leaderboard) DriverPoints() map[string]int {
	driverPoints := make(map[string]int)
	for _, race := range l.Races {
		for _, driver := range race.Results {
			name := race.DriverName(driver)
			driverPoints[name] += race.Points(driver)
		}
	}
	return driverPoints
}

type driverRanking struct {
	Name   string
	Points int
}

func (l *Leaderboard) DriverRankings() []string {
	driverPoints := l.DriverPoints()
	rankings := make([]driverRanking, 0, len(driverPoints))
	for name, points := range driverPoints {
		rankings = append(rankings, driverRanking{Name: name, Points: points})
	}

	sort.Slice(rankings, func(i, j int) bool {
		return rankings[i].Points > rankings[j].Points
	})

	var rankedNames []string
	for _, ranking := range rankings {
		rankedNames = append(rankedNames, ranking.Name)
	}
	return rankedNames
}
